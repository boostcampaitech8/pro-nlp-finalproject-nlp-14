from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, handle_service_error
from app.core.database import get_db
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.meeting import MeetingParticipantResponse
from app.schemas.meeting_participant import (
    AddMeetingParticipantRequest,
    UpdateMeetingParticipantRequest,
)
from app.services.meeting_participant_service import MeetingParticipantService

router = APIRouter(prefix="/meetings/{meeting_id}/participants", tags=["MeetingParticipants"])


def get_participant_service(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> MeetingParticipantService:
    """MeetingParticipantService 의존성"""
    return MeetingParticipantService(db)


@router.post(
    "",
    response_model=MeetingParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def add_meeting_participant(
    meeting_id: UUID,
    data: AddMeetingParticipantRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> MeetingParticipantResponse:
    """회의 참여자 추가"""
    try:
        return await service.add_participant(meeting_id, data, current_user.id)
    except ValueError as e:
        handle_service_error(e)


@router.get(
    "",
    response_model=list[MeetingParticipantResponse],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def list_meeting_participants(
    meeting_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> list[MeetingParticipantResponse]:
    """회의 참여자 목록"""
    try:
        return await service.list_participants(meeting_id, current_user.id)
    except ValueError as e:
        handle_service_error(e)


@router.put(
    "/{user_id}",
    response_model=MeetingParticipantResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_meeting_participant_role(
    meeting_id: UUID,
    user_id: UUID,
    data: UpdateMeetingParticipantRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> MeetingParticipantResponse:
    """참여자 역할 수정"""
    try:
        return await service.update_participant_role(meeting_id, user_id, data, current_user.id)
    except ValueError as e:
        handle_service_error(e)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def remove_meeting_participant(
    meeting_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> None:
    """참여자 제거"""
    try:
        await service.remove_participant(meeting_id, user_id, current_user.id)
    except ValueError as e:
        handle_service_error(e)
