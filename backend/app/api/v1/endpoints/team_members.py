from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.team import TeamMemberResponse
from app.schemas.team_member import InviteTeamMemberRequest, UpdateTeamMemberRequest
from app.services.team_member_service import TeamMemberService

router = APIRouter(prefix="/teams/{team_id}/members", tags=["TeamMembers"])


def get_team_member_service(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> TeamMemberService:
    """TeamMemberService 의존성"""
    return TeamMemberService(db)


@router.post(
    "",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def invite_team_member(
    team_id: UUID,
    data: InviteTeamMemberRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TeamMemberService, Depends(get_team_member_service)],
) -> TeamMemberResponse:
    """팀 멤버 초대"""
    try:
        return await service.invite_member(team_id, data, current_user.id)
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
                detail={"error": "FORBIDDEN", "message": "Only owner or admin can invite members"},
            )
        if error_code == "USER_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "User not found"},
            )
        if error_code == "ALREADY_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "CONFLICT", "message": "User is already a team member"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.get(
    "",
    response_model=list[TeamMemberResponse],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def list_team_members(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TeamMemberService, Depends(get_team_member_service)],
) -> list[TeamMemberResponse]:
    """팀 멤버 목록"""
    try:
        return await service.list_members(team_id, current_user.id)
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


@router.put(
    "/{user_id}",
    response_model=TeamMemberResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_team_member_role(
    team_id: UUID,
    user_id: UUID,
    data: UpdateTeamMemberRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TeamMemberService, Depends(get_team_member_service)],
) -> TeamMemberResponse:
    """멤버 역할 수정"""
    try:
        return await service.update_member_role(team_id, user_id, data, current_user.id)
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
                detail={"error": "FORBIDDEN", "message": "Only owner can change roles"},
            )
        if error_code == "MEMBER_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Member not found"},
            )
        if error_code == "CANNOT_CHANGE_OWNER":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "BAD_REQUEST", "message": "Cannot change owner role"},
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
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[TeamMemberService, Depends(get_team_member_service)],
) -> None:
    """멤버 제거"""
    try:
        await service.remove_member(team_id, user_id, current_user.id)
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
                detail={"error": "FORBIDDEN", "message": "No permission to remove this member"},
            )
        if error_code == "MEMBER_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Member not found"},
            )
        if error_code == "OWNER_CANNOT_LEAVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "BAD_REQUEST", "message": "Owner cannot leave the team"},
            )
        if error_code == "CANNOT_REMOVE_OWNER":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "BAD_REQUEST", "message": "Cannot remove team owner"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )
