"""채팅 API 엔드포인트"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_meeting_participant
from app.core.database import get_db
from app.models.meeting import Meeting
from app.services.chat_service import ChatService

router = APIRouter(prefix="/meetings", tags=["Chat"])


def get_chat_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ChatService:
    """ChatService 의존성"""
    return ChatService(db)


class ChatMessageResponse(BaseModel):
    """채팅 메시지 응답"""

    id: str
    meeting_id: str
    user_id: str
    user_name: str
    content: str
    created_at: str

    class Config:
        from_attributes = True


class ChatMessagesListResponse(BaseModel):
    """채팅 메시지 목록 응답"""

    messages: list[ChatMessageResponse]
    total: int
    page: int
    limit: int


@router.get(
    "/{meeting_id}/chat",
    response_model=ChatMessagesListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_chat_messages(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
):
    """회의 채팅 메시지 조회

    회의의 채팅 메시지를 시간순으로 조회합니다.
    """
    messages = await chat_service.get_messages(meeting.id, page, limit)
    total = await chat_service.get_message_count(meeting.id)

    # 시간순 정렬 (오래된 것 먼저)
    messages.reverse()

    return ChatMessagesListResponse(
        messages=[
            ChatMessageResponse(
                id=str(msg.id),
                meeting_id=str(msg.meeting_id),
                user_id=str(msg.user_id),
                user_name=msg.user.name if msg.user else "Unknown",
                content=msg.content,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages
        ],
        total=total,
        page=page,
        limit=limit,
    )
