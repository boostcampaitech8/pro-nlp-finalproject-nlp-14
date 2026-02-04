"""Spotlight API 엔드포인트"""

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_current_user, get_current_user_from_query
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

# 진행 중인 그래프 실행 태스크 추적 (세션별)
_running_tasks: dict[str, asyncio.Task] = {}

# 그래프 실행 타임아웃 (초) - LLM 응답 지연 고려하여 5분
GRAPH_EXECUTION_TIMEOUT = 300


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


async def _run_graph_to_queue(
    agent_service: SpotlightAgentService,
    queue: asyncio.Queue,
    user_input: str,
    session_id: str,
    user_id: str,
    hitl_action: str | None,
    hitl_params: dict | None,
):
    """그래프 실행을 별도 태스크로 분리 - 클라이언트 disconnect와 무관하게 완료

    타임아웃(5분)이 적용되어 hang 시에도 리소스가 정리됩니다.
    """
    try:
        async with asyncio.timeout(GRAPH_EXECUTION_TIMEOUT):
            async for event in agent_service.process_streaming(
                user_input=user_input,
                session_id=session_id,
                user_id=user_id,
                hitl_action=hitl_action,
                hitl_params=hitl_params,
            ):
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
        await queue.put(None)  # 종료 신호
        # 태스크 추적에서 제거
        _running_tasks.pop(session_id, None)
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

    # 이전에 실행 중인 태스크가 있으면 취소하지 않음 (완료까지 실행)
    # 새 요청에 대한 Queue와 Task 생성
    queue: asyncio.Queue = asyncio.Queue()

    # 그래프 실행을 별도 태스크로 시작 (fire-and-complete)
    task = asyncio.create_task(
        _run_graph_to_queue(
            agent_service=agent_service,
            queue=queue,
            user_input=request.message,
            session_id=session_id,
            user_id=str(current_user.id),
            hitl_action=request.hitl_action,
            hitl_params=request.hitl_params,
        )
    )
    _running_tasks[session_id] = task

    async def event_generator():
        """SSE 이벤트 스트리밍 - Queue에서 이벤트를 읽어 클라이언트에 전송

        클라이언트 disconnect 시 이 generator만 종료되고,
        그래프 실행 태스크는 계속 실행되어 결과가 checkpointer에 저장됩니다.
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
                        yield f"event: message\ndata: {content}\n\n"

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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
