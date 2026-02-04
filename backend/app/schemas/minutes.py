"""Minutes 스키마

Minutes View 전체 응답 (중첩 구조):
- Meeting → Agendas → Decisions → Suggestions/Comments
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .comment import CommentResponse
from .review import DecisionResponse
from .suggestion import SuggestionResponse


class DecisionHistoryItemResponse(BaseModel):
    """Decision 히스토리 아이템 (superseded 체인)"""

    id: str
    content: str
    status: str
    created_at: str = Field(serialization_alias="createdAt")

    class Config:
        populate_by_name = True


class SupersedesResponse(BaseModel):
    """이전 버전 Decision 정보 (GT 표시용)"""

    id: str
    content: str
    meeting_id: str | None = Field(default=None, serialization_alias="meetingId")

    class Config:
        populate_by_name = True


class DecisionWithReviewResponse(DecisionResponse):
    """Decision + Suggestion + Comment 중첩 응답"""

    suggestions: list[SuggestionResponse] = []
    comments: list[CommentResponse] = []

    # 추가 필드: Minutes View에서 필요한 필드들
    meeting_id: str | None = Field(default=None, serialization_alias="meetingId")
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")
    supersedes: SupersedesResponse | None = None
    history: list[DecisionHistoryItemResponse] = []


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
    content: str
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


class MinutesStatusResponse(BaseModel):
    """Minutes 생성 상태 응답"""

    status: str  # "not_started" | "generating" | "completed" | "failed"
