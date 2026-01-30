"""ARQ Worker 설정 및 태스크 정의"""

import logging
from urllib.parse import urlparse
from uuid import UUID

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.neo4j import get_neo4j_driver
from app.repositories.kg.repository import KGRepository
from app.schemas.transcript_ import GetMeetingTranscriptsResponse
from app.services.transcript_service_ import TranscriptService

logger = logging.getLogger(__name__)


async def generate_pr_task(ctx: dict, meeting_id: str) -> dict:
    """PR 생성 태스크

    실시간 STT 완료 후 호출되어 Agenda + Decision을 생성합니다.

    Args:
        ctx: ARQ 컨텍스트
        meeting_id: 회의 ID

    Returns:
        dict: 작업 결과
    """
    meeting_uuid = UUID(meeting_id)

    async with async_session_maker() as db:
        # 새로운 transcripts 테이블에서 데이터 조회
        transcript_service_ = TranscriptService(db)

        try:
            # 1. 트랜스크립트 조회 (새로운 테이블)
            transcript_response: GetMeetingTranscriptsResponse = (
                await transcript_service_.get_meeting_transcripts(meeting_uuid)
            )

            if not transcript_response.full_text:
                logger.error(f"Transcript empty: meeting={meeting_id}")
                return {"status": "failed", "error": "TRANSCRIPT_EMPTY"}

            # 2. generate_pr 워크플로우 실행
            from app.infrastructure.graph.workflows.generate_pr.graph import (
                generate_pr_graph,
            )

            logger.info(f"Starting generate_pr workflow: meeting={meeting_id}")

            result = await generate_pr_graph.ainvoke({
                "generate_pr_meeting_id": meeting_id,
                "generate_pr_transcript_text": transcript_response.full_text,
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
