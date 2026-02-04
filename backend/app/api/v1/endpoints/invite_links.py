from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.invite_link import (
    AcceptInviteResponse,
    InviteLinkResponse,
    InvitePreviewResponse,
)
from app.services.invite_link_service import InviteLinkService

# 팀 스코프 라우터 (인증 필요)
router = APIRouter(prefix="/teams/{team_id}/invite-link", tags=["InviteLinks"])

# 공개 라우터 (미리보기는 인증 불필요)
public_router = APIRouter(prefix="/invite", tags=["InviteLinks"])


def get_invite_link_service(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> InviteLinkService:
    """InviteLinkService 의존성"""
    return InviteLinkService(db)


# ===== 팀 스코프 엔드포인트 (인증 필요) =====


@router.post(
    "",
    response_model=InviteLinkResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def generate_invite_link(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InviteLinkService, Depends(get_invite_link_service)],
) -> InviteLinkResponse:
    """초대 링크 생성 (owner/admin만 가능, 기존 링크 교체)"""
    try:
        return await service.generate_invite_link(team_id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "팀 멤버가 아닙니다"},
            )
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "소유자 또는 관리자만 초대 링크를 생성할 수 있습니다"},
            )
        if error_code == "TEAM_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "팀을 찾을 수 없습니다"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.get(
    "",
    response_model=InviteLinkResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_active_invite_link(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InviteLinkService, Depends(get_invite_link_service)],
) -> InviteLinkResponse:
    """활성 초대 링크 조회 (팀 멤버만 가능)"""
    try:
        result = await service.get_active_invite_link(team_id, current_user.id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "활성화된 초대 링크가 없습니다"},
            )
        return result
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "팀 멤버가 아닙니다"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def deactivate_invite_link(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InviteLinkService, Depends(get_invite_link_service)],
) -> None:
    """초대 링크 비활성화 (owner/admin만 가능)"""
    try:
        await service.deactivate_invite_link(team_id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "팀 멤버가 아닙니다"},
            )
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "소유자 또는 관리자만 초대 링크를 비활성화할 수 있습니다"},
            )
        if error_code == "INVITE_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "비활성화할 초대 링크가 없습니다"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


# ===== 공개 엔드포인트 =====


@public_router.get(
    "/{code}",
    response_model=InvitePreviewResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def preview_invite(
    code: str,
    service: Annotated[InviteLinkService, Depends(get_invite_link_service)],
) -> InvitePreviewResponse:
    """초대 링크 미리보기 (인증 불필요)"""
    try:
        return await service.preview_invite(code)
    except ValueError as e:
        error_code = str(e)
        if error_code == "INVITE_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "초대 링크를 찾을 수 없거나 만료되었습니다"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@public_router.post(
    "/{code}/accept",
    response_model=AcceptInviteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def accept_invite(
    code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[InviteLinkService, Depends(get_invite_link_service)],
) -> AcceptInviteResponse:
    """초대 수락 (인증 필요, MEMBER 역할로 가입)"""
    try:
        return await service.accept_invite(code, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "INVITE_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "초대 링크를 찾을 수 없거나 만료되었습니다"},
            )
        if error_code == "ALREADY_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "CONFLICT", "message": "이미 이 팀의 멤버입니다"},
            )
        if error_code == "TEAM_MEMBER_LIMIT_EXCEEDED":
            settings = get_settings()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "TEAM_MEMBER_LIMIT_EXCEEDED",
                    "message": f"팀 정원이 초과되었습니다 (최대 {settings.max_team_members}명)",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )
