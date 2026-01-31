"""Agenda API 엔드포인트

Agenda 수정/삭제 (Meeting 하위).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.repositories.kg.repository import KGRepository
from app.schemas import ErrorResponse
from app.schemas.agenda import AgendaResponse, UpdateAgendaRequest

router = APIRouter(prefix="/agendas", tags=["Agendas"])


def get_kg_repo() -> KGRepository:
    driver = get_neo4j_driver()
    return KGRepository(driver)


@router.put(
    "/{agenda_id}",
    response_model=AgendaResponse,
    status_code=status.HTTP_200_OK,
    summary="Agenda 수정",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_agenda(
    agenda_id: str,
    request: UpdateAgendaRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[KGRepository, Depends(get_kg_repo)],
) -> AgendaResponse:
    try:
        data = {}
        if request.topic is not None:
            data["topic"] = request.topic
        if request.description is not None:
            data["description"] = request.description
        agenda = await repo.update_agenda(agenda_id, str(current_user.id), data)
        return AgendaResponse(
            id=agenda.id,
            topic=agenda.topic,
            description=agenda.description,
            order=agenda.order,
        )
    except ValueError as e:
        handle_service_error(e)


@router.delete(
    "/{agenda_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Agenda 삭제",
    description="Agenda와 하위 Decision, Comment, Suggestion을 모두 삭제합니다.",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_agenda(
    agenda_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[KGRepository, Depends(get_kg_repo)],
) -> None:
    deleted = await repo.delete_agenda(agenda_id, str(current_user.id))
    if not deleted:
        handle_service_error(ValueError("AGENDA_NOT_FOUND"))
