"""ARQ Worker 설정 및 태스크 정의

# TODO: 태스크가 늘어나면 도메인별로 분리 (stt_tasks.py, pr_tasks.py)
"""

import logging
from urllib.parse import urlparse
from uuid import UUID

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.neo4j import get_neo4j_driver
from app.repositories.kg.repository import KGRepository
from app.services.stt_service import STTService
from app.services.transcript_service import TranscriptService

logger = logging.getLogger(__name__)


async def transcribe_recording_task(ctx: dict, recording_id: str, language: str = "ko") -> dict:
    """개별 녹음 STT 변환 태스크

    Args:
        ctx: ARQ 컨텍스트
        recording_id: 녹음 ID
        language: 우선 언어 코드

    Returns:
        dict: 작업 결과
    """
    recording_uuid = UUID(recording_id)
    meeting_id = None

    async with async_session_maker() as db:
        stt_service = STTService(db)
        transcript_service = TranscriptService(db)

        try:
            # 녹음 조회
            recording = await stt_service.get_recording(recording_uuid)

            if not recording:
                raise ValueError("RECORDING_NOT_FOUND")

            meeting_id = recording.meeting_id
            logger.info(f"Starting transcription task: recording={recording_id}")

            # STT 수행
            result = await stt_service.transcribe_recording(
                recording,
                language=language,
                use_vad=True,
            )

            # 완료 처리
            await stt_service.complete_transcription(recording_uuid, result)

            # 모든 녹음 STT 완료 확인 후 자동 병합
            all_processed = await transcript_service.check_all_recordings_processed(meeting_id)
            if all_processed:
                logger.info(f"All recordings processed, merging utterances: meeting={meeting_id}")
                try:
                    transcript = await transcript_service.get_or_create_transcript(meeting_id)
                    await transcript_service.merge_utterances(meeting_id)
                    logger.info(f"Utterances merged successfully: meeting={meeting_id}")

                    # PR 생성 태스크 큐잉
                    pool = ctx.get("redis")
                    if pool:
                        await pool.enqueue_job("generate_pr_task", str(meeting_id))
                        logger.info(f"generate_pr_task enqueued: meeting={meeting_id}")

                except Exception as merge_error:
                    logger.error(f"Failed to merge utterances: meeting={meeting_id}, error={merge_error}")

            return {
                "status": "success",
                "recording_id": recording_id,
                "text_length": len(result.text),
                "segments_count": len(result.segments),
            }

        except Exception as e:
            logger.exception(f"Transcription task failed: recording={recording_id}")
            await stt_service.fail_transcription(recording_uuid, str(e))

            # 실패해도 다른 녹음이 모두 처리되었으면 병합 시도
            if meeting_id:
                try:
                    all_processed = await transcript_service.check_all_recordings_processed(meeting_id)
                    if all_processed:
                        logger.info(f"All recordings processed (with failures), attempting merge: meeting={meeting_id}")
                        await transcript_service.get_or_create_transcript(meeting_id)
                        await transcript_service.merge_utterances(meeting_id)
                except Exception as merge_error:
                    logger.error(f"Failed to merge utterances after failure: meeting={meeting_id}, error={merge_error}")

            return {
                "status": "failed",
                "recording_id": recording_id,
                "error": str(e),
            }


async def transcribe_meeting_task(ctx: dict, meeting_id: str, language: str = "ko") -> dict:
    """회의 전체 STT 변환 태스크

    모든 녹음을 순차적으로 STT 처리하고 화자별 발화 병합

    Args:
        ctx: ARQ 컨텍스트
        meeting_id: 회의 ID
        language: 우선 언어 코드

    Returns:
        dict: 작업 결과
    """
    meeting_uuid = UUID(meeting_id)

    async with async_session_maker() as db:
        transcript_service = TranscriptService(db)
        stt_service = STTService(db)

        try:
            # 회의 및 녹음 조회
            meeting = await transcript_service.get_meeting_with_recordings(meeting_uuid)

            if not meeting:
                raise ValueError("MEETING_NOT_FOUND")

            # 완료된 녹음 필터링
            from app.models.recording import RecordingStatus
            completed_recordings = [
                r for r in meeting.recordings
                if r.status == RecordingStatus.COMPLETED.value
            ]

            if not completed_recordings:
                raise ValueError("NO_COMPLETED_RECORDINGS")

            logger.info(
                f"Starting meeting transcription: meeting={meeting_id}, "
                f"recordings={len(completed_recordings)}"
            )

            # 각 녹음 STT 처리
            success_count = 0
            fail_count = 0

            for recording in completed_recordings:
                try:
                    # 상태 변경
                    await stt_service.start_transcription(recording.id)

                    # STT 수행
                    result = await stt_service.transcribe_recording(
                        recording,
                        language=language,
                        use_vad=True,
                    )

                    # 완료 처리
                    await stt_service.complete_transcription(recording.id, result)
                    success_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to transcribe recording {recording.id}: {e}"
                    )
                    await stt_service.fail_transcription(recording.id, str(e))
                    fail_count += 1

            # 화자별 발화 병합
            if success_count > 0:
                transcript = await transcript_service.merge_utterances(meeting_uuid)
                logger.info(
                    f"Meeting transcription completed: meeting={meeting_id}, "
                    f"success={success_count}, failed={fail_count}"
                )
                return {
                    "status": "success",
                    "meeting_id": meeting_id,
                    "transcript_id": str(transcript.id),
                    "success_count": success_count,
                    "fail_count": fail_count,
                }
            else:
                await transcript_service.fail_transcription(
                    meeting_uuid,
                    "All recordings failed to transcribe"
                )
                return {
                    "status": "failed",
                    "meeting_id": meeting_id,
                    "error": "All recordings failed to transcribe",
                }

        except Exception as e:
            logger.exception(f"Meeting transcription task failed: meeting={meeting_id}")
            try:
                await transcript_service.fail_transcription(meeting_uuid, str(e))
            except Exception:
                pass
            return {
                "status": "failed",
                "meeting_id": meeting_id,
                "error": str(e),
            }


async def merge_utterances_task(ctx: dict, meeting_id: str) -> dict:
    """화자별 발화 병합 태스크

    모든 녹음 STT 완료 후 호출

    Args:
        ctx: ARQ 컨텍스트
        meeting_id: 회의 ID

    Returns:
        dict: 작업 결과
    """
    meeting_uuid = UUID(meeting_id)

    async with async_session_maker() as db:
        transcript_service = TranscriptService(db)

        try:
            transcript = await transcript_service.merge_utterances(meeting_uuid)

            return {
                "status": "success",
                "meeting_id": meeting_id,
                "transcript_id": str(transcript.id),
                "utterances_count": len(transcript.utterances or []),
            }

        except Exception as e:
            logger.exception(f"Merge utterances task failed: meeting={meeting_id}")
            return {
                "status": "failed",
                "meeting_id": meeting_id,
                "error": str(e),
            }


async def generate_pr_task(ctx: dict, meeting_id: str) -> dict:
    """PR 생성 태스크

    STT 완료 후 호출되어 Agenda + Decision을 생성합니다.

    Args:
        ctx: ARQ 컨텍스트
        meeting_id: 회의 ID

    Returns:
        dict: 작업 결과
    """
    meeting_uuid = UUID(meeting_id)

    async with async_session_maker() as db:
        transcript_service = TranscriptService(db)

        try:
            # 1. 트랜스크립트 조회
            transcript = await transcript_service.get_transcript(meeting_uuid)

            if not transcript:
                logger.error(f"Transcript not found: meeting={meeting_id}")
                return {"status": "failed", "error": "TRANSCRIPT_NOT_FOUND"}

            # 2. generate_pr 워크플로우 실행
            from app.infrastructure.graph.workflows.generate_pr.graph import (
                generate_pr_graph,
            )

            logger.info(f"Starting generate_pr workflow: meeting={meeting_id}")

            result = await generate_pr_graph.ainvoke({
                "generate_pr_meeting_id": meeting_id,
                "generate_pr_transcript_text": transcript.full_text or "",
            })

            agenda_count = len(result.get("generate_pr_agenda_ids", []))
            decision_count = len(result.get("generate_pr_decision_ids", []))

            logger.info(
                f"generate_pr completed: meeting={meeting_id}, "
                f"agendas={agenda_count}, decisions={decision_count}"
            )

            return {
                "status": "success",
                "meeting_id": meeting_id,
                "agenda_count": agenda_count,
                "decision_count": decision_count,
            }

        except Exception as e:
            logger.exception(f"generate_pr task failed: meeting={meeting_id}")
            return {
                "status": "failed",
                "meeting_id": meeting_id,
                "error": str(e),
            }


async def mit_action_task(ctx: dict, decision_id: str) -> dict:
    """Decision에서 Action Item 추출 태스크

    머지된 Decision에서 MIT-action 워크플로우를 실행하여
    Action Item을 추출하고 GraphDB에 저장합니다.

    Args:
        ctx: ARQ 컨텍스트
        decision_id: 머지된 Decision ID

    Returns:
        dict: 작업 결과
    """
    logger.info(f"[mit_action_task] Starting: decision={decision_id}")

    try:
        # 1. Decision 데이터 조회
        driver = get_neo4j_driver()
        kg_repo = KGRepository(driver)
        decision = await kg_repo.get_decision(decision_id)

        if not decision:
            logger.error(f"[mit_action_task] Decision not found: {decision_id}")
            return {"status": "error", "message": "Decision not found"}

        # 2. mit-action 워크플로우 실행
        from app.infrastructure.graph.workflows.mit_action.graph import (
            mit_action_graph,
        )

        result = await mit_action_graph.ainvoke({
            "mit_action_decision": {
                "id": decision.id,
                "content": decision.content,
                "context": decision.context,
            },
            "mit_action_meeting_id": "",  # Decision에서 meeting_id 필요시 별도 조회
        })

        action_count = len(result.get("mit_action_actions", []))
        logger.info(
            f"[mit_action_task] Completed: decision={decision_id}, "
            f"actions={action_count}"
        )

        return {
            "status": "success",
            "decision_id": decision_id,
            "action_count": action_count,
        }

    except Exception as e:
        logger.exception(f"[mit_action_task] Failed: decision={decision_id}")
        return {
            "status": "failed",
            "decision_id": decision_id,
            "error": str(e),
        }


def _get_redis_settings() -> RedisSettings:
    """Redis 연결 설정 생성"""
    settings = get_settings()
    parsed = urlparse(settings.arq_redis_url)

    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=parsed.password,
    )


class WorkerSettings:
    """ARQ Worker 설정"""

    # 등록된 태스크 함수
    functions = [
        transcribe_recording_task,
        transcribe_meeting_task,
        merge_utterances_task,
        generate_pr_task,
        mit_action_task,
    ]

    # Redis 연결 설정 (arq는 인스턴스를 기대)
    redis_settings = _get_redis_settings()

    # Worker 설정
    max_tries = 3                    # 최대 재시도 횟수
    job_timeout = 3600               # 작업 타임아웃 (1시간)
    keep_result = 3600               # 결과 보관 시간 (1시간)
    health_check_interval = 60       # 헬스체크 간격 (60초)
