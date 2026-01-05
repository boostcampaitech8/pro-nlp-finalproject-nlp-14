"""녹음 관련 API 엔드포인트"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.storage import storage_service
from app.models.meeting import Meeting, MeetingParticipant
from app.models.recording import MeetingRecording
from app.models.user import User
from app.schemas.recording import (
    RecordingDownloadResponse,
    RecordingListResponse,
    RecordingResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/meetings", tags=["Recordings"])
security = HTTPBearer()


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


@router.get("/{meeting_id}/recordings", response_model=RecordingListResponse)
async def get_meeting_recordings(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """회의 녹음 목록 조회

    회의 참여자만 조회 가능합니다.
    """
    # 회의 조회 및 참여자 확인
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

    # 참여자인지 확인
    is_participant = any(p.user_id == current_user.id for p in meeting.participants)
    if not is_participant:
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "message": "회의 참여자만 녹음을 조회할 수 있습니다."},
        )

    # 녹음 목록 조회 (user 정보와 함께)
    recordings_query = (
        select(MeetingRecording)
        .options(selectinload(MeetingRecording.user))
        .where(MeetingRecording.meeting_id == meeting_id)
        .order_by(MeetingRecording.started_at.desc())
    )
    recordings_result = await db.execute(recordings_query)
    recordings = recordings_result.scalars().all()

    return RecordingListResponse(
        recordings=[
            RecordingResponse(
                id=r.id,
                meeting_id=r.meeting_id,
                user_id=r.user_id,
                user_name=r.user.name if r.user else None,
                status=r.status,
                started_at=r.started_at,
                ended_at=r.ended_at,
                duration_ms=r.duration_ms,
                file_size_bytes=r.file_size_bytes,
                created_at=r.created_at,
            )
            for r in recordings
        ],
        total=len(recordings),
    )


@router.get("/{meeting_id}/recordings/{recording_id}/download", response_model=RecordingDownloadResponse)
async def get_recording_download_url(
    meeting_id: UUID,
    recording_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """녹음 다운로드 URL 조회

    회의 참여자만 다운로드 가능합니다.
    Presigned URL은 1시간 동안 유효합니다.
    """
    # 회의 조회 및 참여자 확인
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

    # 참여자인지 확인
    is_participant = any(p.user_id == current_user.id for p in meeting.participants)
    if not is_participant:
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "message": "회의 참여자만 녹음을 다운로드할 수 있습니다."},
        )

    # 녹음 조회
    recording_query = select(MeetingRecording).where(
        MeetingRecording.id == recording_id,
        MeetingRecording.meeting_id == meeting_id,
    )
    recording_result = await db.execute(recording_query)
    recording = recording_result.scalar_one_or_none()

    if not recording:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "녹음을 찾을 수 없습니다."},
        )

    # Presigned URL 생성
    try:
        download_url = storage_service.get_recording_url(recording.file_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "STORAGE_ERROR", "message": f"다운로드 URL 생성에 실패했습니다: {str(e)}"},
        )

    return RecordingDownloadResponse(
        recording_id=recording.id,
        download_url=download_url,
        expires_in_seconds=3600,
    )
