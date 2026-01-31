"""KG Comment 엔티티"""

from datetime import datetime

from pydantic import BaseModel


class KGComment(BaseModel):
    """KG Comment 엔티티

    Decision에 대한 댓글. 대댓글 지원 (parent_id).
    @mit 멘션 시 Agent가 자동 응답.
    """

    id: str
    content: str
    author_id: str
    parent_id: str | None = None  # 대댓글인 경우 부모 Comment ID
    decision_id: str  # 속한 Decision
    created_at: datetime
