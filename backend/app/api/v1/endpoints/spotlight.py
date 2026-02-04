"""Spotlight API 엔드포인트"""

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
    """채팅 메시지 전송 (SSE 스트리밍)"""
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

    async def event_generator():
        """SSE 이벤트 스트리밍 - 각 이벤트를 한 번에 전송하여 버퍼링 방지"""
        try:
            async for event in agent_service.process_streaming(
                user_input=request.message,
                session_id=session_id,
                user_id=str(current_user.id),
            ):
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

                # 에러
                elif event_type == "error":
                    error_msg = event.get("error", "알 수 없는 오류")
                    yield f"event: error\ndata: {error_msg}\n\n"

            yield "event: done\ndata: [DONE]\n\n"

        except Exception as e:
            logger.error("Spotlight 채팅 오류: %s", e, exc_info=True)
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
