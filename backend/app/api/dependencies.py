"""공유 API dependencies - 엔드포인트 간 중복 제거"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.meeting import Meeting, MeetingParticipant
from app.models.user import User
from app.services.auth_service import AuthService

security = HTTPBearer()


# ===== Auth Dependencies =====


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    """AuthService 의존성"""
    return AuthService(db)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """현재 사용자 조회"""
    try:
        return await auth_service.get_current_user(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )


# ===== Meeting Validation Dependencies =====


async def get_meeting_with_participants(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Meeting:
    """회의와 참여자 정보를 함께 조회 (404 처리 포함)"""
    query = (
        select(Meeting)
        .options(selectinload(Meeting.participants))
        .where(Meeting.id == meeting_id)
    )
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "회의를 찾을 수 없습니다."},
        )

    return meeting


async def require_meeting_participant(
    meeting: Annotated[Meeting, Depends(get_meeting_with_participants)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Meeting:
    """회의 참여자인지 확인 (403 처리 포함)"""
    is_participant = any(p.user_id == current_user.id for p in meeting.participants)
    if not is_participant:
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "message": "회의 참여자만 접근할 수 있습니다."},
        )
    return meeting
