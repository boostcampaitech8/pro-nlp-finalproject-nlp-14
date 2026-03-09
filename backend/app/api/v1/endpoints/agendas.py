"""Agenda API 엔드포인트

Agenda 수정/삭제 (Meeting 하위).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.repositories.kg.repository import KGRepository
from app.schemas import ErrorResponse
from app.schemas.agenda import AgendaResponse, UpdateAgendaRequest
from app.services.minutes_events import minutes_event_manager

logger = logging.getLogger(__name__)

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

        # SSE 이벤트 발행
        if agenda.meeting_id:
            try:
                await minutes_event_manager.publish(agenda.meeting_id, {
                    "event": "agenda_updated",
                    "agenda_id": agenda_id,
                })
            except Exception as e:
                logger.warning(f"Failed to publish agenda_updated event: {e}")

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
    result = await repo.delete_agenda(agenda_id, str(current_user.id))
    if not result:
        handle_service_error(ValueError("AGENDA_NOT_FOUND"))

    # SSE 이벤트 발행
    meeting_id = result.get("meeting_id")
    if meeting_id:
        try:
            await minutes_event_manager.publish(meeting_id, {
                "event": "agenda_deleted",
                "agenda_id": agenda_id,
            })
        except Exception as e:
            logger.warning(f"Failed to publish agenda_deleted event: {e}")
