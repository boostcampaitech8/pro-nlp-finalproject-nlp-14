"""KG Suggestion 엔티티"""

from datetime import datetime

from pydantic import BaseModel


class KGSuggestion(BaseModel):
    """KG Suggestion 엔티티

    Decision에 대한 수정 제안. Suggestion 생성 시 새로운 Decision도 함께 생성됨.
    """

    id: str
    content: str
    author_id: str
    created_decision_id: str | None = None  # Repository에서 UUID 생성
    created_at: datetime
