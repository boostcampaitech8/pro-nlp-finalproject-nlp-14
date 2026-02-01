"""KG Suggestion 엔티티"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SuggestionStatus = Literal["pending", "accepted", "rejected"]


class KGSuggestion(BaseModel):
    """KG Suggestion 엔티티

    Decision에 대한 수정 제안.
    - pending: 리뷰 대기 중
    - accepted: 수락됨
    - rejected: 거부됨

    Suggestion 생성 시 즉시 draft Decision이 생성됩니다.
    기존 draft Decision은 superseded 상태로 변경됩니다.
    """

    id: str
    content: str
    author_id: str
    status: SuggestionStatus = "pending"
    decision_id: str | None = None  # 원본 Decision (ON 관계)
    created_decision_id: str | None = None  # 생성된 draft Decision (CREATES 관계)
    meeting_id: str | None = None  # Suggestion이 생성된 Meeting 스코프
    created_at: datetime
