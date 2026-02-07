"""Spotlight API 엔드포인트"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_current_user, get_current_user_from_query
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.spotlight import (
    SpotlightChatRequest,
    SpotlightMessageResponse,
    SpotlightSessionResponse,
    SpotlightSessionUpdate,
)
from app.services.spotlight_agent_service import SpotlightAgentService
from app.services.spotlight_session import SpotlightSessionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/spotlight", tags=["Spotlight"])

# 세션별 큐 워커 및 요청 이벤트 큐 추적
_session_workers: dict[str, asyncio.Task] = {}
_pending_event_queues: dict[str, asyncio.Queue] = {}
_instance_id = str(uuid.uuid4())

# 그래프 실행 타임아웃 (초) - LLM 응답 지연 고려하여 5분
GRAPH_EXECUTION_TIMEOUT = 300
QUEUE_LOCK_TTL = 900
QUEUE_PAYLOAD_TTL = 3600
QUEUE_IDLE_TICKS = 5
DRAFT_TTL = 3600
DRAFT_FLUSH_INTERVAL = 0.7


def _queue_key(user_id: str, session_id: str, priority: bool) -> str:
    kind = "priority" if priority else "normal"
    return f"spotlight:queue:{user_id}:{session_id}:{kind}"


def _payload_key(request_id: str) -> str:
    return f"spotlight:queue:payload:{request_id}"


def _lock_key(user_id: str, session_id: str) -> str:
    return f"spotlight:queue:lock:{user_id}:{session_id}"


def _worker_key(user_id: str, session_id: str) -> str:
    return f"{user_id}:{session_id}"


def _draft_key(user_id: str, session_id: str) -> str:
    return f"spotlight:draft:{user_id}:{session_id}"


def _inflight_key(user_id: str, session_id: str) -> str:
    return f"spotlight:inflight:{user_id}:{session_id}"


def get_session_service() -> SpotlightSessionService:
    return SpotlightSessionService()


def get_spotlight_agent_service() -> SpotlightAgentService:
    return SpotlightAgentService()


@router.post(
    "/sessions",
    response_model=SpotlightSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    current_user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SpotlightSessionService, Depends(get_session_service)],
):
    """새 Spotlight 세션 생성"""
    session = await session_service.create_session(str(current_user.id))
    return SpotlightSessionResponse(
        id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=session.message_count,
    )


@router.get("/sessions", response_model=list[SpotlightSessionResponse])
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SpotlightSessionService, Depends(get_session_service)],
):
    """세션 목록 조회"""
    sessions = await session_service.list_sessions(str(current_user.id))
    return [
        SpotlightSessionResponse(
            id=s.session_id,
            user_id=s.user_id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=s.message_count,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SpotlightSessionResponse)
async def get_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SpotlightSessionService, Depends(get_session_service)],
):
    """세션 상세 조회"""
    session = await session_service.get_session(str(current_user.id), session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "세션을 찾을 수 없습니다."},
        )

    return SpotlightSessionResponse(
        id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=session.message_count,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SpotlightSessionService, Depends(get_session_service)],
):
    """세션 삭제"""
    deleted = await session_service.delete_session(str(current_user.id), session_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "세션을 찾을 수 없습니다."},
        )


@router.patch("/sessions/{session_id}", response_model=SpotlightSessionResponse)
async def update_session(
    session_id: str,
    request: SpotlightSessionUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SpotlightSessionService, Depends(get_session_service)],
):
    """세션 제목 수정"""
    session = await session_service.update_session(
        str(current_user.id), session_id, title=request.title
    )
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "세션을 찾을 수 없습니다."},
        )

    return SpotlightSessionResponse(
        id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=session.message_count,
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[SpotlightMessageResponse],
)
async def get_session_messages(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session_service: Annotated[SpotlightSessionService, Depends(get_session_service)],
    agent_service: Annotated[
        SpotlightAgentService, Depends(get_spotlight_agent_service)
    ],
):
    """세션의 메시지 히스토리 조회"""
    # 세션 존재 확인
    session = await session_service.get_session(str(current_user.id), session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "세션을 찾을 수 없습니다."},
        )

    # LangGraph checkpointer에서 히스토리 조회
    history = await agent_service.get_history(session_id)
    return [SpotlightMessageResponse(**msg) for msg in history]


async def _enqueue_request(
    *,
    user_id: str,
    session_id: str,
    request_id: str,
    message: str,
    hitl_action: str | None,
    hitl_params: dict | None,
) -> None:
    redis = await get_redis()
    payload = {
        "request_id": request_id,
        "user_id": user_id,
        "session_id": session_id,
        "message": message,
        "hitl_action": hitl_action,
        "hitl_params": hitl_params,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis.set(_payload_key(request_id), json.dumps(payload), ex=QUEUE_PAYLOAD_TTL)
    queue_key = _queue_key(user_id, session_id, priority=hitl_action is not None)
    await redis.rpush(queue_key, request_id)


async def _process_session_queue(
    agent_service: SpotlightAgentService,
    user_id: str,
    session_id: str,
) -> None:
    redis = await get_redis()
    lock_key = _lock_key(user_id, session_id)
    lock_acquired = await redis.set(lock_key, _instance_id, nx=True, ex=QUEUE_LOCK_TTL)
    if not lock_acquired:
        return

    try:
        idle_ticks = 0
        while idle_ticks < QUEUE_IDLE_TICKS:
            await redis.expire(lock_key, QUEUE_LOCK_TTL)
            result = await redis.blpop(
                [
                    _queue_key(user_id, session_id, priority=True),
                    _queue_key(user_id, session_id, priority=False),
                ],
                timeout=1,
            )
            if not result:
                idle_ticks += 1
                continue

            idle_ticks = 0
            _, request_id = result
            payload_raw = await redis.get(_payload_key(request_id))
            if not payload_raw:
                _pending_event_queues.pop(request_id, None)
                continue

            payload = json.loads(payload_raw)
            event_queue = _pending_event_queues.get(request_id)
            if event_queue is None:
                event_queue = asyncio.Queue()
                _pending_event_queues[request_id] = event_queue

            try:
                await _run_graph_to_queue(
                    agent_service=agent_service,
                    queue=event_queue,
                    user_input=payload.get("message", ""),
                    session_id=payload.get("session_id", session_id),
                    user_id=payload.get("user_id", user_id),
                    hitl_action=payload.get("hitl_action"),
                    hitl_params=payload.get("hitl_params"),
                    request_id=payload.get("request_id"),
                )
            finally:
                await redis.delete(_payload_key(request_id))
                _pending_event_queues.pop(request_id, None)

    finally:
        current_value = await redis.get(lock_key)
        if current_value == _instance_id:
            await redis.delete(lock_key)
        _session_workers.pop(_worker_key(user_id, session_id), None)


def _ensure_session_worker(
    agent_service: SpotlightAgentService,
    user_id: str,
    session_id: str,
) -> None:
    key = _worker_key(user_id, session_id)
    existing = _session_workers.get(key)
    if existing and not existing.done():
        return

    task = asyncio.create_task(_process_session_queue(agent_service, user_id, session_id))
    _session_workers[key] = task


async def _run_graph_to_queue(
    agent_service: SpotlightAgentService,
    queue: asyncio.Queue,
    user_input: str,
    session_id: str,
    user_id: str,
    hitl_action: str | None,
    hitl_params: dict | None,
    request_id: str | None = None,
):
    """그래프 실행을 별도 태스크로 분리 - 클라이언트 disconnect와 무관하게 완료

    타임아웃(5분)이 적용되어 hang 시에도 리소스가 정리됩니다.
    """
    redis = await get_redis()
    draft_content = ""
    last_flush = 0.0
    completed = False
    hitl_pending = False
    had_error = False

    if request_id:
        await redis.set(_inflight_key(user_id, session_id), request_id, ex=DRAFT_TTL)
        logger.info("Inflight 요청 설정: session=%s, request=%s", session_id, request_id)

    try:
        async with asyncio.timeout(GRAPH_EXECUTION_TIMEOUT):
            async for event in agent_service.process_streaming(
                user_input=user_input,
                session_id=session_id,
                user_id=user_id,
                hitl_action=hitl_action,
                hitl_params=hitl_params,
            ):
                event_type = event.get("type")
                tag = event.get("tag")

                if event_type == "token" and tag == "generator_token":
                    content = event.get("content", "")
                    if content:
                        draft_content += content
                        now = time.monotonic()
                        if now - last_flush >= DRAFT_FLUSH_INTERVAL:
                            payload = {
                                "request_id": request_id,
                                "content": draft_content,
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }
                            await redis.set(
                                _draft_key(user_id, session_id),
                                json.dumps(payload, ensure_ascii=False),
                                ex=DRAFT_TTL,
                            )
                            logger.debug(
                                "Draft 갱신: session=%s, request=%s, length=%d",
                                session_id,
                                request_id,
                                len(draft_content),
                            )
                            last_flush = now
                elif event_type == "done":
                    completed = True
                elif event_type == "hitl_request":
                    hitl_pending = True
                elif event_type == "error":
                    had_error = True

                await queue.put(event)
    except asyncio.TimeoutError:
        logger.error(
            "그래프 실행 타임아웃 (session=%s, timeout=%ds)",
            session_id,
            GRAPH_EXECUTION_TIMEOUT,
        )
        await queue.put({
            "type": "error",
            "error": "요청 처리 시간이 초과되었습니다. 다시 시도해 주세요.",
        })
    except Exception as e:
        logger.error("그래프 실행 오류 (session=%s): %s", session_id, e, exc_info=True)
        await queue.put({"type": "error", "error": str(e)})
    finally:
        if had_error and draft_content:
            payload = {
                "request_id": request_id,
                "content": draft_content,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await redis.set(
                _draft_key(user_id, session_id),
                json.dumps(payload, ensure_ascii=False),
                ex=DRAFT_TTL,
            )
            logger.info(
                "Draft 유지(에러): session=%s, request=%s, length=%d",
                session_id,
                request_id,
                len(draft_content),
            )
        if completed or hitl_pending:
            await redis.delete(_draft_key(user_id, session_id))
            logger.info("Draft 삭제: session=%s, request=%s", session_id, request_id)
        if request_id:
            await redis.delete(_inflight_key(user_id, session_id))
            logger.info("Inflight 해제: session=%s, request=%s", session_id, request_id)
        await queue.put(None)  # 종료 신호
        logger.info("그래프 실행 완료 (session=%s)", session_id)


@router.post("/sessions/{session_id}/chat")
async def chat_stream(
    session_id: str,
    request: SpotlightChatRequest,
    current_user: Annotated[User, Depends(get_current_user_from_query)],
    session_service: Annotated[SpotlightSessionService, Depends(get_session_service)],
    agent_service: Annotated[
        SpotlightAgentService, Depends(get_spotlight_agent_service)
    ],
):
    """채팅 메시지 전송 (SSE 스트리밍)

    그래프 실행은 별도 태스크로 분리되어 클라이언트가 연결을 끊어도 완료됩니다.
    완료된 응답은 LangGraph checkpointer에 저장되어 세션 복귀 시 조회 가능합니다.
    """
    # 세션 존재 확인
    session = await session_service.get_session(str(current_user.id), session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"error": "SESSION_NOT_FOUND", "message": "세션이 만료되었습니다."},
        )

    # 첫 메시지면 제목 자동 생성 (첫 20자)
    if session.message_count == 0:
        title = request.message[:20] + ("..." if len(request.message) > 20 else "")
        await session_service.update_session(
            str(current_user.id), session_id, title=title
        )

    # 메시지 카운트 증가 + TTL 갱신
    await session_service.update_session(
        str(current_user.id), session_id, increment_message_count=True
    )

    # 새 요청을 세션 큐에 등록 (HITL 응답은 priority)
    request_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _pending_event_queues[request_id] = queue
    await queue.put({
        "type": "status",
        "tag": "queue",
        "message": "요청을 접수했습니다...",
    })

    await _enqueue_request(
        user_id=str(current_user.id),
        session_id=session_id,
        request_id=request_id,
        message=request.message,
        hitl_action=request.hitl_action,
        hitl_params=request.hitl_params,
    )
    _ensure_session_worker(agent_service, str(current_user.id), session_id)

    async def event_generator():
        """SSE 이벤트 스트리밍 - Queue에서 이벤트를 읽어 클라이언트에 전송

        클라이언트 disconnect 시 이 generator만 종료되고,
        그래프 실행은 계속 진행되어 결과가 checkpointer에 저장됩니다.
        """
        try:
            while True:
                try:
                    # 타임아웃으로 클라이언트 연결 상태 확인
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    # 타임아웃 - 연결 유지 ping
                    yield ": ping\n\n"
                    continue

                if event is None:
                    # 그래프 실행 완료
                    break

                event_type = event.get("type")
                tag = event.get("tag")

                # 최종 답변 텍스트 - 토큰 단위로 즉시 전송
                if event_type == "token" and tag == "generator_token":
                    content = event.get("content", "")
                    if content:
                        # SSE spec: 줄바꿈이 포함된 데이터는 각 줄을 별도 data: 필드로 전송
                        data_lines = '\n'.join(f'data: {line}' for line in content.split('\n'))
                        yield f"event: message\n{data_lines}\n\n"

                # 상태 메시지
                elif event_type == "node_start" and tag == "status":
                    node = event.get("node")
                    status_map = {
                        "planner": "생각을 정리하고 있어요...",
                        "mit_tools": "관련 정보를 찾고 있어요...",
                        "tools": "도구를 실행하고 있어요...",
                        "evaluator": "답변을 다듬고 있어요...",
                        "generator": "답변을 준비 중입니다...",
                    }
                    status_msg = status_map.get(node)
                    if status_msg:
                        yield f"event: status\ndata: {status_msg}\n\n"
                elif event_type == "status":
                    message = event.get("message")
                    if message:
                        yield f"event: status\ndata: {message}\n\n"

                # 도구 실행
                elif event_type == "tool_start" and tag == "tool_event":
                    tool_name = event.get("tool_name", "unknown")
                    yield f"event: status\ndata: '{tool_name}' 도구를 실행하고 있어요...\n\n"

                elif event_type == "tool_end" and tag == "tool_event":
                    tool_name = event.get("tool_name", "unknown")
                    yield f"event: status\ndata: '{tool_name}' 완료\n\n"

                # === HITL 확인 요청 ===
                elif event_type == "hitl_request":
                    hitl_data = json.dumps({
                        "tool_name": event.get("tool_name"),
                        "params": event.get("params", {}),
                        "params_display": event.get("params_display", {}),
                        "message": event.get("message", ""),
                        "required_fields": event.get("required_fields", []),
                        "display_template": event.get("display_template"),
                        "hitl_request_id": event.get("hitl_request_id"),
                    }, ensure_ascii=False)
                    yield f"event: hitl_request\ndata: {hitl_data}\n\n"
                    # HITL pending 상태이므로 스트림 종료
                    yield "event: done\ndata: [HITL_PENDING]\n\n"
                    return  # 사용자 확인 대기

                # 에러
                elif event_type == "error":
                    error_msg = event.get("error", "알 수 없는 오류")
                    yield f"event: error\ndata: {error_msg}\n\n"

                # 완료
                elif event_type == "done":
                    pass  # 아래에서 done 이벤트 전송

            yield "event: done\ndata: [DONE]\n\n"

        except asyncio.CancelledError:
            # 클라이언트 disconnect - 그래프 태스크는 계속 실행됨
            logger.info("클라이언트 연결 종료 (session=%s) - 그래프 실행은 계속됨", session_id)
        except Exception as e:
            logger.error("SSE 스트리밍 오류 (session=%s): %s", session_id, e, exc_info=True)
            yield f"event: error\ndata: {str(e)}\n\n"
        finally:
            _pending_event_queues.pop(request_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
