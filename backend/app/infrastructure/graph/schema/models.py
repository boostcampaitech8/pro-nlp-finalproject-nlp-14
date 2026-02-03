"""Graph 공통 Pydantic 모델

워크플로우에서 사용하는 데이터 구조 정의
"""

from typing import Literal

from pydantic import BaseModel, Field


class ActionItemData(BaseModel):
    """Action Item 데이터 구조

    KGActionItem과 필드명 통일 (변환 로직 단순화)
    """

    content: str = Field(..., description="할 일 내용")
    due_date: str | None = Field(None, description="기한 (ISO 8601)")
    assignee_id: str | None = Field(None, description="담당자 ID")
    assignee_name: str | None = Field(None, description="담당자 이름 (추론된)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="추출 신뢰도")


class ActionItemEvalResult(BaseModel):
    """Action Item 평가 결과"""

    passed: bool = Field(..., description="평가 통과 여부")
    reason: str = Field("", description="평가 결과 사유")
    score: float = Field(0.0, ge=0.0, le=1.0, description="평가 점수")


class NewDecisionResult(BaseModel):
    """AI가 생성한 새 Decision 결과

    Suggestion을 반영하여 AI가 생성한 개선된 Decision 내용
    """
    new_decision_content: str = Field(..., description="개선된 Decision 내용")
    supersedes_reason: str = Field("", description="대체 사유 (왜 이렇게 변경했는지)")
    confidence: Literal["low", "medium", "high"] = Field("medium", description="AI 신뢰도")
