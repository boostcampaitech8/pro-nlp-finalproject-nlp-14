"""녹음 관련 API 엔드포인트"""

import logging
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_meeting_participant
from app.core.config import get_settings
from app.core.constants import PRESIGNED_URL_EXPIRATION
from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.recording import MeetingRecording, RecordingStatus
from app.models.user import User
from app.schemas.recording import (
    RecordingConfirmRequest,
    RecordingDownloadResponse,
    RecordingListResponse,
    RecordingResponse,
    RecordingUploadUrlRequest,
    RecordingUploadUrlResponse,
)
from app.schemas.team import PaginationMeta
from app.services.recording_service import RecordingService

logger = logging.getLogger(__name__)


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

router = APIRouter(prefix="/meetings", tags=["Recordings"])


def get_recording_service(db: Annotated[AsyncSession, Depends(get_db)]) -> RecordingService:
    """RecordingService 의존성"""
    return RecordingService(db)


@router.get("/{meeting_id}/recordings", response_model=RecordingListResponse)
async def get_meeting_recordings(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
):
    """회의 녹음 목록 조회

    회의 참여자만 조회 가능합니다.
    """
    recordings = await recording_service.get_meeting_recordings(meeting.id)
    total = len(recordings)

    return RecordingListResponse(
        items=[
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
                transcript_text=r.transcript_text,
                transcript_language=r.transcript_language,
                transcription_started_at=r.transcription_started_at,
                transcription_completed_at=r.transcription_completed_at,
                transcription_error=r.transcription_error,
            )
            for r in recordings
        ],
        meta=PaginationMeta(
            page=1,
            limit=total if total > 0 else 20,
            total=total,
            total_pages=1,
        ),
    )


@router.get("/{meeting_id}/recordings/{recording_id}/download", response_model=RecordingDownloadResponse)
async def get_recording_download_url(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    recording_id: UUID,
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
):
    """녹음 다운로드 URL 조회

    회의 참여자만 다운로드 가능합니다.
    Presigned URL은 1시간 동안 유효합니다.
    """
    recording = await recording_service.get_recording_by_id(recording_id, meeting.id)

    if not recording:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "녹음을 찾을 수 없습니다."},
        )

    try:
        download_url = recording_service.get_download_url(recording.file_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "STORAGE_ERROR", "message": f"다운로드 URL 생성에 실패했습니다: {str(e)}"},
        )

    return RecordingDownloadResponse(
        recording_id=recording.id,
        download_url=download_url,
        expires_in_seconds=PRESIGNED_URL_EXPIRATION,
    )


@router.get("/{meeting_id}/recordings/{recording_id}/file")
async def download_recording_file(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    recording_id: UUID,
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
):
    """녹음 파일 직접 다운로드

    회의 참여자만 다운로드 가능합니다.
    파일을 직접 스트리밍합니다.
    """
    recording = await recording_service.get_recording_by_id(recording_id, meeting.id)

    if not recording:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "녹음을 찾을 수 없습니다."},
        )

    try:
        file_data = recording_service.get_file_content(recording.file_path)
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
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    current_user: Annotated[User, Depends(get_current_user)],
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
    file: UploadFile = File(...),
    started_at: datetime = Form(..., alias="startedAt"),
    ended_at: datetime = Form(..., alias="endedAt"),
    duration_ms: int = Form(..., alias="durationMs"),
):
    """녹음 파일 업로드

    클라이언트에서 MediaRecorder로 녹음한 파일을 업로드합니다.
    회의 참여자만 업로드 가능합니다.
    """
    # 파일 유효성 검사
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": "파일이 필요합니다."},
        )

    # 파일 읽기
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": "빈 파일은 업로드할 수 없습니다."},
        )

    try:
        recording = await recording_service.upload_recording_directly(
            meeting_id=meeting.id,
            user_id=current_user.id,
            file_content=content,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
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

    except ValueError as e:
        error_code = str(e)
        if error_code == "FILE_TOO_LARGE":
            raise HTTPException(
                status_code=400,
                detail={"error": "BAD_REQUEST", "message": "파일 크기는 500MB를 초과할 수 없습니다."},
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": str(e)},
        )
    except Exception as e:
        logger.error(f"Failed to upload recording: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "UPLOAD_FAILED", "message": f"녹음 업로드에 실패했습니다: {str(e)}"},
        )


@router.post("/{meeting_id}/recordings/upload-url", response_model=RecordingUploadUrlResponse, status_code=status.HTTP_201_CREATED)
async def get_recording_upload_url(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    request: RecordingUploadUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
):
    """녹음 업로드용 Presigned URL 발급

    클라이언트에서 대용량 녹음 파일을 직접 MinIO에 업로드하기 위한
    Presigned URL을 발급합니다.

    1. 이 엔드포인트로 presigned URL 요청
    2. 반환된 uploadUrl로 파일 직접 업로드 (PUT)
    3. /recordings/{recording_id}/confirm 으로 업로드 완료 확인
    """
    try:
        upload_url, file_path, recording_id = await recording_service.create_recording_upload(
            meeting_id=meeting.id,
            user_id=current_user.id,
            file_size_bytes=request.file_size_bytes,
            started_at=request.started_at,
            ended_at=request.ended_at,
            duration_ms=request.duration_ms,
        )

        return RecordingUploadUrlResponse(
            recording_id=recording_id,
            upload_url=upload_url,
            file_path=file_path,
            expires_in_seconds=PRESIGNED_URL_EXPIRATION,
        )

    except ValueError as e:
        error_code = str(e)
        if error_code == "FILE_TOO_LARGE":
            raise HTTPException(
                status_code=400,
                detail={"error": "BAD_REQUEST", "message": "파일 크기는 500MB를 초과할 수 없습니다."},
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": str(e)},
        )

    except Exception as e:
        logger.error(f"Failed to generate upload URL: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "UPLOAD_URL_FAILED", "message": f"업로드 URL 생성에 실패했습니다: {str(e)}"},
        )


@router.post("/{meeting_id}/recordings/{recording_id}/confirm", response_model=RecordingResponse)
async def confirm_recording_upload(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    recording_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
    request: RecordingConfirmRequest | None = None,
):
    """녹음 업로드 완료 확인

    Presigned URL로 MinIO에 직접 업로드한 후,
    이 엔드포인트를 호출하여 업로드 완료를 확인합니다.

    서버에서 파일 존재 여부를 확인하고 상태를 completed로 변경합니다.
    업로드 완료 후 자동으로 STT 변환 작업을 큐잉합니다.
    """
    try:
        recording = await recording_service.complete_recording_upload(recording_id, meeting.id)

        # STT 작업 자동 큐잉
        try:
            pool = await get_arq_pool()
            await pool.enqueue_job(
                "transcribe_recording_task",
                str(recording_id),
                "ko",  # 기본 한국어
            )
            await pool.close()
            logger.info(f"STT task queued for recording: {recording_id}")
        except Exception as stt_error:
            # STT 큐잉 실패해도 녹음 완료 응답은 반환
            logger.error(f"Failed to queue STT task: {stt_error}")

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

    except ValueError as e:
        error_code = str(e)
        if error_code == "RECORDING_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "녹음을 찾을 수 없습니다."},
            )
        if error_code == "FILE_NOT_FOUND":
            raise HTTPException(
                status_code=400,
                detail={"error": "BAD_REQUEST", "message": "업로드된 파일을 찾을 수 없습니다."},
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": str(e)},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm recording upload: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "CONFIRM_FAILED", "message": f"업로드 확인에 실패했습니다: {str(e)}"},
        )
