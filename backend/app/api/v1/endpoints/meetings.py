from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import ErrorResponse
from app.schemas.meeting import (
    CreateMeetingRequest,
    MeetingListResponse,
    MeetingResponse,
    MeetingWithParticipantsResponse,
    UpdateMeetingRequest,
)
from app.services.auth_service import AuthService
from app.services.meeting_service import MeetingService

router = APIRouter(tags=["Meetings"])
security = HTTPBearer()


def get_meeting_service(db: Annotated[AsyncSession, Depends(get_db)]) -> MeetingService:
    """MeetingService 의존성"""
    return MeetingService(db)


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


# /api/v1/teams/{team_id}/meetings 엔드포인트
team_meetings_router = APIRouter(prefix="/teams/{team_id}/meetings", tags=["Meetings"])


@team_meetings_router.post(
    "",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_meeting(
    team_id: UUID,
    data: CreateMeetingRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> MeetingResponse:
    """회의 생성"""
    try:
        return await meeting_service.create_meeting(team_id, data, user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@team_meetings_router.get(
    "",
    response_model=MeetingListResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def list_team_meetings(
    team_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
) -> MeetingListResponse:
    """팀 회의 목록"""
    try:
        return await meeting_service.list_team_meetings(
            team_id, user_id, page, limit, status
        )
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


# /api/v1/meetings/{meeting_id} 엔드포인트
@router.get(
    "/meetings/{meeting_id}",
    response_model=MeetingWithParticipantsResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_meeting(
    meeting_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> MeetingWithParticipantsResponse:
    """회의 상세 조회"""
    try:
        return await meeting_service.get_meeting(meeting_id, user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.put(
    "/meetings/{meeting_id}",
    response_model=MeetingResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_meeting(
    meeting_id: UUID,
    data: UpdateMeetingRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> MeetingResponse:
    """회의 수정"""
    try:
        return await meeting_service.update_meeting(meeting_id, data, user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "No permission to update meeting"},
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.delete(
    "/meetings/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_meeting(
    meeting_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> None:
    """회의 삭제"""
    try:
        await meeting_service.delete_meeting(meeting_id, user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "No permission to delete meeting"},
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )
