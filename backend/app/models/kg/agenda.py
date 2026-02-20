"""KG Agenda 엔티티"""

from pydantic import BaseModel


class KGAgenda(BaseModel):
    """KG Agenda 엔티티"""

    id: str
    topic: str
    description: str | None = None
    order: int = 0

    # 관계 정보 (조회 시 포함)
    meeting_id: str | None = None
