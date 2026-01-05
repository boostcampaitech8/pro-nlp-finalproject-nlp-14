from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import ErrorResponse
from app.schemas.team import (
    CreateTeamRequest,
    TeamListResponse,
    TeamResponse,
    TeamWithMembersResponse,
    UpdateTeamRequest,
)
from app.services.auth_service import AuthService
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])
security = HTTPBearer()


def get_team_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TeamService:
    """TeamService 의존성"""
    return TeamService(db)


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
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def create_team(
    data: CreateTeamRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> TeamResponse:
    """팀 생성"""
    try:
        return await team_service.create_team(data, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.get(
    "",
    response_model=TeamListResponse,
    responses={401: {"model": ErrorResponse}},
)
async def list_my_teams(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> TeamListResponse:
    """내 팀 목록"""
    return await team_service.list_my_teams(user_id, page, limit)


@router.get(
    "/{team_id}",
    response_model=TeamWithMembersResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_team(
    team_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> TeamWithMembersResponse:
    """팀 상세 조회"""
    try:
        return await team_service.get_team(team_id, user_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        if error_code == "TEAM_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Team not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.put(
    "/{team_id}",
    response_model=TeamResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_team(
    team_id: UUID,
    data: UpdateTeamRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> TeamResponse:
    """팀 수정"""
    try:
        return await team_service.update_team(team_id, data, user_id)
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
                detail={"error": "FORBIDDEN", "message": "Only owner or admin can update team"},
            )
        if error_code == "TEAM_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Team not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_team(
    team_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> None:
    """팀 삭제"""
    try:
        await team_service.delete_team(team_id, user_id)
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
                detail={"error": "FORBIDDEN", "message": "Only owner can delete team"},
            )
        if error_code == "TEAM_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Team not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )
