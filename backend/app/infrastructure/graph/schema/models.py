"""Graph 공통 Pydantic 모델

워크플로우에서 사용하는 데이터 구조 정의
"""

from pydantic import BaseModel, Field


class ActionItemData(BaseModel):
    """Action Item 데이터 구조

    NOTE: GraphDB 스키마 확정 전 임시 구조. 추후 변경될 수 있음.
    """

    content: str = Field(..., description="할 일 내용")
    assignee_id: str | None = Field(None, description="담당자 ID")
    assignee_name: str | None = Field(None, description="담당자 이름 (추론된)")
    deadline: str | None = Field(None, description="기한 (ISO 8601)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="추출 신뢰도")


class ActionItemEvalResult(BaseModel):
    """Action Item 평가 결과"""

    passed: bool = Field(..., description="평가 통과 여부")
    reason: str = Field("", description="평가 결과 사유")
    score: float = Field(0.0, ge=0.0, le=1.0, description="평가 점수")
