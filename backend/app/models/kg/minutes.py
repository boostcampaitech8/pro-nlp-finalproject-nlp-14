"""KG Minutes 엔티티"""

from datetime import datetime

from pydantic import BaseModel


class KGSpanRef(BaseModel):
    """근거 참조 (Utterance 기반)"""

    transcript_id: str = "meeting-transcript"
    start_utt_id: str
    end_utt_id: str
    sub_start: int | None = None
    sub_end: int | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    topic_id: str | None = None
    topic_name: str | None = None


class KGMinutesDecision(BaseModel):
    """회의록 내 결정사항"""

    id: str
    content: str
    context: str | None = None
    agenda_topic: str | None = None
    evidence: list[KGSpanRef] = []


class KGMinutesAgenda(BaseModel):
    """회의록 내 아젠다"""

    id: str
    topic: str
    description: str | None = None
    evidence: list[KGSpanRef] = []
    decision: KGMinutesDecision | None = None


class KGMinutesActionItem(BaseModel):
    """회의록 내 액션아이템"""

    id: str
    content: str
    assignee: str | None = None
    due_date: str | None = None


class KGMinutes(BaseModel):
    """KG Minutes 엔티티"""

    id: str
    meeting_id: str
    summary: str
    created_at: datetime

    # 연관 데이터 (조회 시 포함)
    agendas: list[KGMinutesAgenda] = []
    decisions: list[KGMinutesDecision] = []
    action_items: list[KGMinutesActionItem] = []
