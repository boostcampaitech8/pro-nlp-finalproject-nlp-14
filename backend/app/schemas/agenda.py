"""Agenda 스키마"""

from pydantic import BaseModel


class UpdateAgendaRequest(BaseModel):
    """Agenda 수정 요청"""

    topic: str | None = None
    description: str | None = None


class AgendaResponse(BaseModel):
    """Agenda 응답"""

    id: str
    topic: str
    description: str | None = None
    order: int
