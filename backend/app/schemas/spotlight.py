"""Spotlight 채팅 스키마"""

from datetime import datetime

from pydantic import BaseModel


class SpotlightSessionCreate(BaseModel):
    """세션 생성 요청 (body 없음, 자동 생성)"""

    pass


class SpotlightSessionResponse(BaseModel):
    """세션 응답"""

    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class SpotlightSessionUpdate(BaseModel):
    """세션 수정 요청"""

    title: str


class SpotlightChatRequest(BaseModel):
    """채팅 요청"""

    message: str


class SpotlightMessageResponse(BaseModel):
    """메시지 히스토리 아이템"""

    role: str  # "user" | "assistant"
    content: str
