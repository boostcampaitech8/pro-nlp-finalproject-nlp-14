"""ARQ Worker 설정 및 태스크 정의 (OTel 계측 포함)"""

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse
from uuid import UUID

from arq.connections import RedisSettings
from opentelemetry import trace

from app.core.config import get_settings
from app.infrastructure.graph.integration.langfuse import get_runnable_config
from app.core.database import async_session_maker
from app.core.neo4j import get_neo4j_driver
from app.core.telemetry import get_mit_metrics, get_tracer, setup_telemetry
from app.repositories.kg.repository import KGRepository
from app.schemas.transcript import GetMeetingTranscriptsResponse
from app.services.minutes_events import minutes_event_manager
from app.services.transcript_service import TranscriptService

logger = logging.getLogger(__name__)

T = TypeVar("T")


def traced_task(task_name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """ARQ 태스크에 OTel 트레이싱 + 메트릭 추가 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(ctx: dict, *args: Any, **kwargs: Any) -> T:
            tracer = get_tracer()
            metrics = get_mit_metrics()

            with tracer.start_as_current_span(
                f"arq.task.{task_name}",
                kind=trace.SpanKind.CONSUMER,
            ) as span:
                span.set_attribute("arq.task.name", task_name)
                span.set_attribute("arq.task.args", str(args)[:200])

                start_time = time.perf_counter()
                try:
                    result = await func(ctx, *args, **kwargs)

                    # 성공 메트릭
                    span.set_attribute("arq.task.status", "success")
                    if metrics:
                        metrics.arq_task_result.add(
                            1, {"task_name": task_name, "status": "success"}
                        )
                    return result

                except Exception as e:
                    # 실패 메트릭
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    if metrics:
                        metrics.arq_task_result.add(
                            1, {"task_name": task_name, "status": "failed"}
                        )
                    raise

                finally:
                    # 실행 시간 메트릭
                    duration = time.perf_counter() - start_time
                    if metrics:
                        metrics.arq_task_duration.record(
                            duration, {"task_name": task_name}
                        )

        return wrapper  # type: ignore
    return decorator


@traced_task("generate_pr_task")
async def generate_pr_task(
    ctx: dict,
    meeting_id: str,
    realtime_topics: list[dict] | None = None,
) -> dict:
    """PR 생성 태스크

    실시간 STT 완료 후 호출되어 Agenda + Decision을 생성합니다.

    Args:
        ctx: ARQ 컨텍스트
        meeting_id: 회의 ID
        realtime_topics: API에서 전달받은 실시간 L1 토픽 스냅샷

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

            logger.info(
                "Starting generate_pr workflow: meeting=%s, realtime_topics=%d",
                meeting_id,
                len(realtime_topics or []),
            )

            result = await generate_pr_graph.ainvoke(
                {
                    "generate_pr_meeting_id": meeting_id,
                    "generate_pr_transcript_text": transcript_response.full_text,
                    "generate_pr_transcript_utterances": [
                        {
                            "id": str(utterance.id),
                            "speaker_name": utterance.speaker_name,
                            "text": utterance.text,
                            "start_ms": utterance.start_ms,
                            "end_ms": utterance.end_ms,
                        }
                        for utterance in transcript_response.utterances
                    ],
                    "generate_pr_realtime_topics": realtime_topics or [],
                },
                config=get_runnable_config(
                    trace_name="PR Generation",
                    metadata={"meeting_id": meeting_id, "workflow_version": "2.0"},
                    mode="voice",
                    tags=["workflow", "generate_pr"],
                ),
            )

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


@traced_task("mit_action_task")
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

        result = await mit_action_graph.ainvoke(
            {
                "mit_action_decision": {
                    "id": decision.id,
                    "content": decision.content,
                    "context": decision.context,
                },
                "mit_action_meeting_id": "",  # Decision에서 meeting_id 필요시 별도 조회
            },
            config=get_runnable_config(
                trace_name="MIT Action",
                metadata={"decision_id": decision_id, "workflow_version": "2.0"},
                mode="voice",
                tags=["workflow", "mit_action"],
            ),
        )

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


@traced_task("process_suggestion_task")
async def process_suggestion_task(
    ctx: dict, suggestion_id: str, decision_id: str, content: str
) -> dict:
    """Suggestion AI 분석 태스크

    Suggestion을 반영하여 AI가 새로운 Decision 내용을 생성합니다.

    NOTE: 새로운 설계에서는 Suggestion 생성 시 즉시 draft Decision이 생성됩니다.
    이 태스크는 AI가 새 Decision 내용을 생성하고, 해당 draft Decision을 업데이트합니다.

    워크플로우:
    1. Decision 컨텍스트 조회
    2. Transcript 조회 (SpanRef 텍스트 추출용)
    3. LangGraph mit-suggestion 워크플로우 실행 (AI가 새 Decision 내용 생성)
    4. 생성된 draft Decision 내용 업데이트
    5. Suggestion 상태 업데이트 (accepted)

    Args:
        ctx: ARQ 컨텍스트
        suggestion_id: Suggestion ID
        decision_id: 원본 Decision ID
        content: Suggestion 내용

    Returns:
        dict: 작업 결과
    """
    logger.info(f"[process_suggestion_task] Starting: suggestion={suggestion_id}")

    try:
        # 1. Decision 컨텍스트 조회
        driver = get_neo4j_driver()
        kg_repo = KGRepository(driver)
        decision = await kg_repo.get_decision(decision_id)

        if not decision:
            logger.error(f"[process_suggestion_task] Decision not found: {decision_id}")
            await kg_repo.update_suggestion_status(suggestion_id, "rejected")
            return {"status": "error", "message": "Decision not found"}

        # 2. Suggestion 정보 조회 (created_decision_id 획득)
        suggestion = await kg_repo.get_suggestion(suggestion_id)
        if not suggestion:
            logger.error(f"[process_suggestion_task] Suggestion not found: {suggestion_id}")
            return {"status": "error", "message": "Suggestion not found"}

        # 3. Transcript 조회 (SpanRef 텍스트 추출용)
        utterances_data: list[dict] = []
        if decision.meeting_id:
            try:
                async with async_session_maker() as db:
                    transcript_service = TranscriptService(db)
                    transcript_response = await transcript_service.get_meeting_transcripts(
                        UUID(decision.meeting_id)
                    )
                    utterances_data = [
                        {
                            "speaker_name": utt.speaker_name,
                            "text": utt.text,
                            "start_ms": utt.start_ms,
                            "end_ms": utt.end_ms,
                        }
                        for utt in transcript_response.utterances
                    ]
                    logger.info(
                        f"[process_suggestion_task] Loaded {len(utterances_data)} utterances"
                    )
            except Exception as e:
                logger.warning(f"[process_suggestion_task] Failed to load transcripts: {e}")

        # 4. mit-suggestion 워크플로우 실행
        from app.infrastructure.graph.workflows.mit_suggestion.graph import (
            mit_suggestion_graph,
        )

        result = await mit_suggestion_graph.ainvoke(
            {
                "mit_suggestion_id": suggestion_id,
                "mit_suggestion_content": content,
                "mit_suggestion_decision_id": decision_id,
                "mit_suggestion_decision_content": decision.content,
                "mit_suggestion_decision_context": decision.context,
                "mit_suggestion_agenda_topic": decision.agenda_topic,
                "mit_suggestion_meeting_id": decision.meeting_id,
                "mit_suggestion_utterances": utterances_data if utterances_data else None,
            },
            config=get_runnable_config(
                trace_name="MIT Suggestion",
                metadata={"suggestion_id": suggestion_id, "decision_id": decision_id, "workflow_version": "2.0"},
                mode="voice",
                tags=["workflow", "suggestion"],
            ),
        )

        # 4. 워크플로우 결과 추출
        new_content = result.get("mit_suggestion_new_decision_content")
        supersedes_reason = result.get("mit_suggestion_supersedes_reason", "")
        confidence = result.get("mit_suggestion_confidence", "medium")

        # 5. draft Decision 내용 업데이트 (이미 생성된 draft Decision)
        if suggestion.created_decision_id and new_content:
            await kg_repo.update_decision_content(
                suggestion.created_decision_id,
                content=new_content,
                context=f"[AI 생성] {supersedes_reason}",
            )
            logger.info(
                f"[process_suggestion_task] Draft decision updated: "
                f"decision={suggestion.created_decision_id}, confidence={confidence}"
            )

        # 6. Suggestion 상태 업데이트
        await kg_repo.update_suggestion_status(suggestion_id, "accepted")

        logger.info(
            f"[process_suggestion_task] Completed: suggestion={suggestion_id}, "
            f"confidence={confidence}"
        )

        # 7. Minutes SSE 이벤트 발행 (draft Decision 업데이트 알림)
        if decision.meeting_id:
            await minutes_event_manager.publish(decision.meeting_id, {
                "event": "suggestion_processed",
                "suggestion_id": suggestion_id,
                "decision_id": decision_id,
                "created_decision_id": suggestion.created_decision_id,
                "confidence": confidence,
            })

        return {
            "status": "success",
            "suggestion_id": suggestion_id,
            "confidence": confidence,
            "new_decision_content": new_content[:100] + "..." if new_content and len(new_content) > 100 else new_content,
        }

    except Exception as e:
        logger.exception(f"[process_suggestion_task] Failed: suggestion={suggestion_id}")
        # H3: 실패 시 rejected로 변경 (status 업데이트 실패도 로깅)
        try:
            driver = get_neo4j_driver()
            kg_repo = KGRepository(driver)
            await kg_repo.update_suggestion_status(suggestion_id, "rejected")
        except Exception as status_error:
            logger.error(
                f"[process_suggestion_task] Failed to update suggestion status to rejected: "
                f"suggestion={suggestion_id}, error={status_error}"
            )
        return {
            "status": "failed",
            "suggestion_id": suggestion_id,
            "error": str(e),
        }


@traced_task("process_mit_mention")
async def process_mit_mention(
    ctx: dict, comment_id: str, decision_id: str, content: str
) -> dict:
    """@mit 멘션 처리 태스크

    Comment에서 @mit 멘션 시 Agent가 Decision 컨텍스트를 바탕으로
    응답을 생성하고 대댓글로 작성합니다.

    Args:
        ctx: ARQ 컨텍스트
        comment_id: 원본 Comment ID
        decision_id: Decision ID
        content: Comment 내용

    Returns:
        dict: 작업 결과
    """
    logger.info(f"[process_mit_mention] Starting: comment={comment_id}")

    try:
        # 1. Decision 컨텍스트 조회
        driver = get_neo4j_driver()
        kg_repo = KGRepository(driver)
        decision = await kg_repo.get_decision(decision_id)

        if not decision:
            logger.error(f"[process_mit_mention] Decision not found: {decision_id}")
            await kg_repo.update_comment_pending_agent_reply(comment_id, False)

            # Decision을 찾을 수 없는 경우 에러 응답 생성
            agent_id = await kg_repo.get_or_create_system_agent()
            error_message = "죄송합니다. 결정사항을 찾을 수 없습니다. 페이지를 새로고침해 주세요."
            error_reply = await kg_repo.create_reply(
                comment_id=comment_id,
                user_id=agent_id,
                content=error_message,
                pending_agent_reply=False,
                is_error_response=True,
            )

            # Minutes SSE 이벤트 발행 (에러 응답)
            # Decision이 없으므로 meeting_id를 조회할 수 없음 - 이벤트 발행 스킵

            return {"status": "error", "message": "Decision not found"}

        # 2. Decision에 달린 이전 논의 이력 조회
        thread_history = await kg_repo.get_decision_thread_history(decision_id)
        logger.info(f"[process_mit_mention] Thread history: {len(thread_history)} messages")

        # 3. mit_mention 워크플로우 실행
        from app.infrastructure.graph.workflows.mit_mention.graph import (
            mit_mention_graph,
        )

        result = await mit_mention_graph.ainvoke(
            {
                "mit_mention_comment_id": comment_id,
                "mit_mention_content": content,
                "mit_mention_decision_id": decision_id,
                "mit_mention_decision_content": decision.content,
                "mit_mention_decision_context": decision.context,
                "mit_mention_thread_history": thread_history,
                "mit_mention_meeting_id": decision.meeting_id,  # Meeting ID 추가
                "mit_mention_retry_count": 0,
            },
            config=get_runnable_config(
                trace_name="MIT Mention",
                mode="voice",
                tags=["workflow", "mit_mention"],
                metadata={
                    "comment_id": comment_id,
                    "decision_id": decision_id,
                    "workflow_version": "2.0",
                },
            ),
        )

        # 3. AI 응답으로 대댓글 생성
        ai_response = result.get("mit_mention_response", "")
        is_error = False

        if not ai_response:
            logger.error(f"[process_mit_mention] No response generated: comment={comment_id}")
            ai_response = "죄송합니다. 응답을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."
            is_error = True

        # MIT Agent 시스템 사용자로 대댓글 작성
        agent_id = await kg_repo.get_or_create_system_agent()

        reply = await kg_repo.create_reply(
            comment_id=comment_id,
            user_id=agent_id,
            content=ai_response,
            pending_agent_reply=False,
            is_error_response=is_error,
        )

        # 원본 comment의 pending_agent_reply 해제
        await kg_repo.update_comment_pending_agent_reply(comment_id, False)

        logger.info(f"[process_mit_mention] Reply created: {reply.id}")

        # Minutes SSE 이벤트 발행
        if decision.meeting_id:
            await minutes_event_manager.publish(decision.meeting_id, {
                "event": "comment_reply_ready",
                "decision_id": decision_id,
                "comment_id": comment_id,
                "reply_id": reply.id,
            })
            logger.info(f"[process_mit_mention] SSE event published: meeting={decision.meeting_id}")

        return {
            "status": "success",
            "comment_id": comment_id,
            "reply_id": reply.id,
            "response": ai_response[:100] + "..." if len(ai_response) > 100 else ai_response,
        }

    except Exception as e:
        logger.exception(f"[process_mit_mention] Failed: comment={comment_id}")

        # 실패 시 사용자 친화적인 에러 메시지로 대댓글 생성
        try:
            driver = get_neo4j_driver()
            kg_repo = KGRepository(driver)

            # 에러 타입별 메시지 생성
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                error_message = "죄송합니다. 응답 생성 시간이 초과되었습니다. 다시 시도해 주세요."
            elif "context" in error_str or "decision" in error_str:
                error_message = "죄송합니다. 컨텍스트 수집 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
            else:
                error_message = "죄송합니다. AI 응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

            # 에러 응답 대댓글 생성
            agent_id = await kg_repo.get_or_create_system_agent()
            error_reply = await kg_repo.create_reply(
                comment_id=comment_id,
                user_id=agent_id,
                content=error_message,
                pending_agent_reply=False,
                is_error_response=True,
            )

            # pending 상태 해제
            await kg_repo.update_comment_pending_agent_reply(comment_id, False)

            # Minutes SSE 이벤트 발행 (에러 응답)
            try:
                error_decision = await kg_repo.get_decision(decision_id)
                if error_decision and error_decision.meeting_id:
                    await minutes_event_manager.publish(error_decision.meeting_id, {
                        "event": "comment_reply_ready",
                        "decision_id": decision_id,
                        "comment_id": comment_id,
                        "reply_id": error_reply.id,
                    })
            except Exception:
                pass  # 이벤트 발행 실패해도 에러 응답은 이미 생성됨
        except Exception:
            # 에러 응답 생성 실패 시에도 최소한 pending 상태는 해제
            try:
                await kg_repo.update_comment_pending_agent_reply(comment_id, False)
            except Exception:
                pass  # Best effort

        return {
            "status": "failed",
            "comment_id": comment_id,
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


async def startup(ctx: dict) -> None:
    """Worker 시작 시 Telemetry 초기화"""
    setup_telemetry("mit-arq-worker", "0.1.0")
    logger.info("ARQ Worker started with telemetry")


async def shutdown(ctx: dict) -> None:
    """Worker 종료 시 정리"""
    logger.info("ARQ Worker shutting down")


class WorkerSettings:
    """ARQ Worker 설정"""

    # 등록된 태스크 함수
    functions = [
        generate_pr_task,
        mit_action_task,
        process_suggestion_task,
        process_mit_mention,
    ]

    # Redis 연결 설정 (arq는 인스턴스를 기대)
    redis_settings = _get_redis_settings()

    # 라이프사이클 콜백
    on_startup = startup
    on_shutdown = shutdown

    # Worker 설정
    max_tries = 3                    # 최대 재시도 횟수
    job_timeout = 3600               # 작업 타임아웃 (1시간)
    keep_result = 3600               # 결과 보관 시간 (1시간)
    health_check_interval = 60       # 헬스체크 간격 (60초)
