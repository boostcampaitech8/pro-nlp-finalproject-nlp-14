"""녹음 관련 API 엔드포인트"""

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.storage import storage_service
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus
from app.models.recording import MeetingRecording, RecordingStatus
from app.models.user import User
from app.schemas.recording import (
    RecordingDownloadResponse,
    RecordingListResponse,
    RecordingResponse,
)
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

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


@router.get("/{meeting_id}/recordings/{recording_id}/file")
async def download_recording_file(
    meeting_id: UUID,
    recording_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """녹음 파일 직접 다운로드

    회의 참여자만 다운로드 가능합니다.
    파일을 직접 스트리밍합니다.
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

    # MinIO에서 파일 다운로드
    try:
        file_data = storage_service.get_recording_file(recording.file_path)
    except Exception as e:
        logger.error(f"Failed to download recording: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "STORAGE_ERROR", "message": f"파일 다운로드에 실패했습니다: {str(e)}"},
        )

    # 파일명 생성
    filename = recording.file_path.split("/")[-1]

    return Response(
        content=file_data,
        media_type="audio/webm",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_data)),
        },
    )


@router.post("/{meeting_id}/recordings", response_model=RecordingResponse, status_code=status.HTTP_201_CREATED)
async def upload_recording(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    started_at: datetime = Form(..., alias="startedAt"),
    ended_at: datetime = Form(..., alias="endedAt"),
    duration_ms: int = Form(..., alias="durationMs"),
):
    """녹음 파일 업로드

    클라이언트에서 MediaRecorder로 녹음한 파일을 업로드합니다.
    회의 참여자만 업로드 가능합니다.
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
            detail={"error": "FORBIDDEN", "message": "회의 참여자만 녹음을 업로드할 수 있습니다."},
        )

    # 파일 유효성 검사
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": "파일이 필요합니다."},
        )

    # 파일 크기 제한 (500MB)
    MAX_FILE_SIZE = 500 * 1024 * 1024
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": "파일 크기는 500MB를 초과할 수 없습니다."},
        )

    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": "빈 파일은 업로드할 수 없습니다."},
        )

    try:
        # MinIO에 업로드
        timestamp = started_at.strftime("%Y%m%d_%H%M%S")
        file_path = storage_service.upload_recording(
            meeting_id=str(meeting_id),
            user_id=str(current_user.id),
            timestamp=timestamp,
            data=content,
        )

        # DB에 녹음 메타데이터 저장
        recording = MeetingRecording(
            meeting_id=meeting_id,
            user_id=current_user.id,
            file_path=file_path,
            status=RecordingStatus.COMPLETED.value,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            file_size_bytes=file_size,
        )
        db.add(recording)
        await db.commit()
        await db.refresh(recording)

        logger.info(
            f"Recording uploaded: meeting={meeting_id}, user={current_user.id}, "
            f"size={file_size}, duration={duration_ms}ms"
        )

        return RecordingResponse(
            id=recording.id,
            meeting_id=recording.meeting_id,
            user_id=recording.user_id,
            user_name=current_user.name,
            status=recording.status,
            started_at=recording.started_at,
            ended_at=recording.ended_at,
            duration_ms=recording.duration_ms,
            file_size_bytes=recording.file_size_bytes,
            created_at=recording.created_at,
        )

    except Exception as e:
        logger.error(f"Failed to upload recording: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "UPLOAD_FAILED", "message": f"녹음 업로드에 실패했습니다: {str(e)}"},
        )
