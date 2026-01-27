"""KG Decision 엔티티"""

from datetime import datetime

from pydantic import BaseModel


class KGDecision(BaseModel):
    """KG Decision 엔티티"""

    id: str
    content: str
    status: str  # pending, approved, rejected, merged
    context: str | None = None
    created_at: datetime

    # 관계 정보 (조회 시 포함)
    agenda_id: str | None = None
    agenda_topic: str | None = None
    meeting_title: str | None = None
    approvers: list[str] = []  # user_ids
    rejectors: list[str] = []  # user_ids
