"""KG ActionItem 엔티티"""

from datetime import date

from pydantic import BaseModel


class KGActionItem(BaseModel):
    """KG ActionItem 엔티티"""

    id: str
    title: str
    description: str | None = None
    status: str  # pending, in_progress, completed
    due_date: date | None = None

    # 관계 정보 (조회 시 포함)
    assignee_id: str | None = None
    assignee_name: str | None = None
    decision_id: str | None = None
    from_decision: str | None = None  # decision content
