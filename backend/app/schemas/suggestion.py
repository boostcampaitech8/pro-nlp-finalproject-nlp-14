"""Suggestion 스키마"""

from datetime import datetime

from pydantic import BaseModel, Field

from .common_brief import DecisionBriefResponse, UserBriefResponse


class CreateSuggestionRequest(BaseModel):
    """Suggestion 생성 요청"""

    content: str


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
