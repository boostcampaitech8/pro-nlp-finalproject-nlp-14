"""KG Minutes 엔티티"""

from datetime import datetime

from pydantic import BaseModel


class KGMinutesDecision(BaseModel):
    """회의록 내 결정사항"""

    id: str
    content: str
    context: str | None = None
    agenda_topic: str | None = None


class KGMinutesActionItem(BaseModel):
    """회의록 내 액션아이템"""

    id: str
    title: str
    description: str | None = None
    assignee: str | None = None
    due_date: str | None = None


class KGMinutes(BaseModel):
    """KG Minutes 엔티티"""

    id: str
    meeting_id: str
    summary: str
    created_at: datetime

    # 연관 데이터 (조회 시 포함)
    decisions: list[KGMinutesDecision] = []
    action_items: list[KGMinutesActionItem] = []
