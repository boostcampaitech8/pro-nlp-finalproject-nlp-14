"""Simple Router shared output schema."""

from pydantic import BaseModel, Field


class SimpleRouterOutput(BaseModel):
    """간단한 쿼리 라우터의 판정 결과"""

    is_simple_query: bool = Field(description="간단한 쿼리 여부 (True면 planning 스킵)")
    category: str = Field(
        description=(
            "쿼리 카테고리 (greeting, sentiment, acknowledgment, "
            "nonsense, general_knowledge, guide, unavailable, other)"
        )
    )
    simple_response: str | None = Field(
        default=None,
        description="간단한 쿼리일 경우 제안 응답 (응답 생성기에서 참고용)",
    )
    confidence: float = Field(description="판정 신뢰도 (0.0-1.0)")
    reasoning: str = Field(description="판정 근거")
