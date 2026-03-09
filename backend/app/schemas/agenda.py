"""Agenda 스키마"""

from pydantic import BaseModel


class UpdateAgendaRequest(BaseModel):
    """Agenda 수정 요청"""

    topic: str | None = None
    description: str | None = None


class ConfirmAgendaMatchRequest(BaseModel):
    """아젠다 매칭 확인 요청"""

    action: str  # "confirm" | "ignore"
    candidate_id: str | None = None  # confirm 시 필요


class AgendaResponse(BaseModel):
    """Agenda 응답"""

    id: str
    topic: str
    description: str | None = None
    order: int


class AgendaMatchResponse(BaseModel):
    """Agenda 매칭 확인 응답"""

    id: str
    topic: str
    description: str | None = None
    order: int
    match_status: str | None = None
    match_score: float | None = None
    candidate_agenda_id: str | None = None
