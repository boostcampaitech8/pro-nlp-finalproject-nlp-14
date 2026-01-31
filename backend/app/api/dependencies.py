"""공유 API dependencies - 엔드포인트 간 중복 제거"""

from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.user import User
from app.services.auth.auth_service import AuthService

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
        select(Meeting).options(selectinload(Meeting.participants)).where(Meeting.id == meeting_id)
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


# ===== Service Error Handling =====

# 서비스 레이어에서 발생하는 에러 코드와 HTTP 응답 매핑
# (status_code, error_code, message)
SERVICE_ERROR_MAPPING: dict[str, tuple[int, str, str]] = {
    # 공통
    "MEETING_NOT_FOUND": (404, "NOT_FOUND", "Meeting not found"),
    "PARTICIPANT_NOT_FOUND": (404, "NOT_FOUND", "Participant not found"),
    "NOT_TEAM_MEMBER": (403, "FORBIDDEN", "Not a team member"),
    "PERMISSION_DENIED": (403, "FORBIDDEN", "Permission denied"),
    # 참여자 관련
    "USER_NOT_TEAM_MEMBER": (400, "BAD_REQUEST", "User is not a team member"),
    "ALREADY_PARTICIPANT": (409, "CONFLICT", "User is already a participant"),
    "INVALID_ROLE": (400, "BAD_REQUEST", "Invalid role"),
    # Decision 관련
    "DECISION_NOT_FOUND": (404, "NOT_FOUND", "Decision not found"),
    "COMMENT_NOT_FOUND": (404, "NOT_FOUND", "Comment not found"),
    "SUGGESTION_NOT_FOUND": (404, "NOT_FOUND", "Suggestion not found"),
    "AGENDA_NOT_FOUND": (404, "NOT_FOUND", "Agenda not found"),
    "ACTION_ITEM_NOT_FOUND": (404, "NOT_FOUND", "ActionItem not found"),
}


def handle_service_error(error: ValueError, default_message: str = "Validation error") -> None:
    """서비스 레이어 에러를 HTTPException으로 변환

    Args:
        error: 서비스에서 발생한 ValueError (에러 코드가 str로 전달됨)
        default_message: 매핑되지 않은 에러의 기본 메시지

    Raises:
        HTTPException: 매핑된 HTTP 에러 응답
    """
    error_code = str(error)

    if error_code in SERVICE_ERROR_MAPPING:
        status_code, code, message = SERVICE_ERROR_MAPPING[error_code]
        raise HTTPException(
            status_code=status_code,
            detail={"error": code, "message": message},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": "VALIDATION_ERROR", "message": default_message},
    )


# ===== ARQ Dependencies =====


async def get_arq_pool() -> ArqRedis:
    """ARQ Redis 연결 풀"""
    settings = get_settings()
    parsed = urlparse(settings.arq_redis_url)

    redis_settings = RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=parsed.password,
    )

    return await create_pool(redis_settings)
