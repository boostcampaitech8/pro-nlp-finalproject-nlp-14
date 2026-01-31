"""Agenda 스키마"""

from pydantic import BaseModel


class UpdateAgendaRequest(BaseModel):
    """Agenda 수정 요청"""

    topic: str | None = None
    description: str | None = None
