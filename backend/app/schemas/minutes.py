"""Minutes 스키마

Minutes View 전체 응답 (중첩 구조):
- Meeting → Agendas → Decisions → Suggestions/Comments
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .comment import CommentResponse
from .review import DecisionResponse
from .suggestion import SuggestionResponse


class DecisionWithReviewResponse(DecisionResponse):
    """Decision + Suggestion + Comment 중첩 응답"""

    suggestions: list[SuggestionResponse] = []
    comments: list[CommentResponse] = []


class AgendaWithDecisionsResponse(BaseModel):
    """Agenda + Decisions 응답"""

    id: str
    topic: str
    description: str | None = None
    order: int
    decisions: list[DecisionWithReviewResponse] = []


class ActionItemBriefResponse(BaseModel):
    """ActionItem 간략 응답 (Minutes 내 표시용)"""

    id: str
    title: str
    status: str
    assignee_id: str | None = Field(default=None, serialization_alias="assigneeId")
    due_date: datetime | None = Field(default=None, serialization_alias="dueDate")

    class Config:
        populate_by_name = True


class MinutesResponse(BaseModel):
    """Minutes View 전체 응답 (중첩 구조)"""

    meeting_id: str = Field(serialization_alias="meetingId")
    summary: str
    agendas: list[AgendaWithDecisionsResponse]
    action_items: list[ActionItemBriefResponse] = Field(
        default=[], serialization_alias="actionItems"
    )

    class Config:
        populate_by_name = True
