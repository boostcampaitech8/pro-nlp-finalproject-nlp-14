"""Decision 리뷰 스키마"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DecisionReviewRequest(BaseModel):
    """리뷰 생성 요청"""

    action: Literal["approve", "reject"] = Field(
        description="리뷰 액션 (approve 또는 reject)"
    )


class UpdateDecisionRequest(BaseModel):
    """Decision 수정 요청"""

    content: str | None = None
    context: str | None = None


class DecisionReviewResponse(BaseModel):
    """리뷰 생성 응답"""

    decision_id: str = Field(serialization_alias="decisionId")
    action: str
    success: bool
    merged: bool = False
    status: str
    approvers_count: int = Field(serialization_alias="approversCount")
    participants_count: int = Field(serialization_alias="participantsCount")

    class Config:
        populate_by_name = True


class DecisionResponse(BaseModel):
    """Decision 상세 응답"""

    id: str
    content: str
    context: str | None = None
    status: str
    agenda_topic: str | None = Field(default=None, serialization_alias="agendaTopic")
    meeting_title: str | None = Field(default=None, serialization_alias="meetingTitle")
    approvers: list[str] = []
    rejectors: list[str] = []
    created_at: datetime = Field(serialization_alias="createdAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class DecisionListResponse(BaseModel):
    """Decision 목록 응답 (회의별)"""

    meeting_id: str = Field(serialization_alias="meetingId")
    decisions: list[DecisionResponse]

    class Config:
        populate_by_name = True
