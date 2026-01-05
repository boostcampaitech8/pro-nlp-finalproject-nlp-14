from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import ErrorResponse
from app.schemas.meeting import MeetingParticipantResponse
from app.schemas.meeting_participant import (
    AddMeetingParticipantRequest,
    UpdateMeetingParticipantRequest,
)
from app.services.auth_service import AuthService
from app.services.meeting_participant_service import MeetingParticipantService

router = APIRouter(prefix="/meetings/{meeting_id}/participants", tags=["MeetingParticipants"])
security = HTTPBearer()


def get_participant_service(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> MeetingParticipantService:
    """MeetingParticipantService 의존성"""
    return MeetingParticipantService(db)


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    """AuthService 의존성"""
    return AuthService(db)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UUID:
    """현재 사용자 ID 조회"""
    try:
        user = await auth_service.get_current_user(credentials.credentials)
        return user.id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )


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
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> MeetingParticipantResponse:
    """회의 참여자 추가"""
    try:
        return await service.add_participant(meeting_id, data, user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "No permission to add participants"},
            )
        if error_code == "USER_NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "BAD_REQUEST", "message": "User is not a team member"},
            )
        if error_code == "ALREADY_PARTICIPANT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "CONFLICT", "message": "User is already a participant"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


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
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> list[MeetingParticipantResponse]:
    """회의 참여자 목록"""
    try:
        return await service.list_participants(meeting_id, user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


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
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> MeetingParticipantResponse:
    """참여자 역할 수정"""
    try:
        return await service.update_participant_role(meeting_id, user_id, data, current_user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "No permission to change roles"},
            )
        if error_code == "PARTICIPANT_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Participant not found"},
            )
        if error_code == "INVALID_ROLE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "BAD_REQUEST", "message": "Invalid role"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


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
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    service: Annotated[MeetingParticipantService, Depends(get_participant_service)],
) -> None:
    """참여자 제거"""
    try:
        await service.remove_participant(meeting_id, user_id, current_user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "No permission to remove participants"},
            )
        if error_code == "PARTICIPANT_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Participant not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )
