"""KG Meeting 엔티티"""

from datetime import datetime

from pydantic import BaseModel


class KGMeeting(BaseModel):
    """KG Meeting 엔티티"""

    id: str
    title: str
    status: str  # scheduled, in_progress, completed

    # 관계 정보 (조회 시 포함)
    team_id: str | None = None
    team_name: str | None = None
    participant_ids: list[str] = []
    created_at: datetime | None = None
