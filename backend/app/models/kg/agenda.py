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

    # 하이브리드 아젠다 매칭 정보
    match_status: str | None = None  # "matched" | "needs_confirmation" | "new" | None
    match_score: float | None = None  # 0.0 ~ 1.0
    candidate_agenda_id: str | None = None  # 매칭된 기존 아젠다 ID (확인 대기 중)
