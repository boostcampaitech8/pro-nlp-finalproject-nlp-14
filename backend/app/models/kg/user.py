"""KG User 엔티티"""

from pydantic import BaseModel


class KGUser(BaseModel):
    """KG User 엔티티"""

    id: str
    name: str
    email: str

    # 관계 정보 (조회 시 포함)
    team_ids: list[str] = []
