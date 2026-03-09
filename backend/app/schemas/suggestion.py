"""Suggestion 스키마"""

from datetime import datetime

from pydantic import BaseModel, Field

from .common_brief import DecisionBriefResponse, UserBriefResponse


class CreateSuggestionRequest(BaseModel):
    """Suggestion 생성 요청

    Suggestion 생성 시 즉시 draft Decision이 함께 생성됩니다.
    기존 draft Decision은 superseded 상태로 변경됩니다.
    """

    content: str
    meeting_id: str = Field(
        ...,
        description="Suggestion이 생성되는 Meeting ID (스코프)",
        alias="meetingId",
        serialization_alias="meetingId",
    )

    class Config:
        populate_by_name = True


class SuggestionResponse(BaseModel):
    """Suggestion 응답"""

    id: str
    content: str
    author: UserBriefResponse
    created_decision: DecisionBriefResponse | None = Field(
        default=None, serialization_alias="createdDecision"
    )
    created_at: datetime = Field(serialization_alias="createdAt")

    class Config:
        populate_by_name = True
