"""KG Team 엔티티"""

from pydantic import BaseModel


class KGTeam(BaseModel):
    """KG Team 엔티티"""

    id: str
    name: str
    description: str | None = None

    # 관계 정보 (조회 시 포함)
    member_ids: list[str] = []
