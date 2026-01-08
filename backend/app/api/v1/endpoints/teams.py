from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.team import (
    CreateTeamRequest,
    TeamListResponse,
    TeamResponse,
    TeamWithMembersResponse,
    UpdateTeamRequest,
)
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])


def get_team_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TeamService:
    """TeamService 의존성"""
    return TeamService(db)


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
    current_user: Annotated[User, Depends(get_current_user)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> TeamResponse:
    """팀 생성"""
    try:
        return await team_service.create_team(data, current_user.id)
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
    current_user: Annotated[User, Depends(get_current_user)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> TeamListResponse:
    """내 팀 목록"""
    return await team_service.list_my_teams(current_user.id, page, limit)


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
    current_user: Annotated[User, Depends(get_current_user)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> TeamWithMembersResponse:
    """팀 상세 조회"""
    try:
        return await team_service.get_team(team_id, current_user.id)
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
    current_user: Annotated[User, Depends(get_current_user)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> TeamResponse:
    """팀 수정"""
    try:
        return await team_service.update_team(team_id, data, current_user.id)
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
    current_user: Annotated[User, Depends(get_current_user)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> None:
    """팀 삭제"""
    try:
        await team_service.delete_team(team_id, current_user.id)
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
