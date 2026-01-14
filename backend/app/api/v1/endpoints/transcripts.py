"""트랜스크립트 관련 API 엔드포인트"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_arq_pool, require_meeting_participant
from app.core.database import get_db
from app.models.meeting import Meeting
from app.core.storage import storage_service
from app.schemas.transcript import (
    MeetingTranscriptResponse,
    TranscribeRequest,
    TranscribeResponse,
    TranscriptDownloadResponse,
    TranscriptStatusResponse,
    UtteranceResponse,
)
from app.services.transcript_service import TranscriptService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["Transcripts"])


def get_transcript_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TranscriptService:
    """TranscriptService 의존성"""
    return TranscriptService(db)


@router.post(
    "/{meeting_id}/transcribe",
    response_model=TranscribeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_transcription(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    transcript_service: Annotated[TranscriptService, Depends(get_transcript_service)],
    request: TranscribeRequest | None = None,
):
    """회의 STT 변환 시작

    회의의 모든 완료된 녹음에 대해 STT 작업을 시작합니다.
    비동기로 처리되며, 상태는 /transcript/status로 확인할 수 있습니다.
    """
    language = request.language if request else "ko"

    try:
        # 트랜스크립트 생성 또는 조회
        transcript = await transcript_service.start_transcription(meeting.id)

        # ARQ 작업 큐잉
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "transcribe_meeting_task",
            str(meeting.id),
            language,
        )
        await pool.close()

        return TranscribeResponse(
            transcript_id=transcript.id,
            status=transcript.status,
            message="STT 변환 작업이 시작되었습니다.",
        )

    except ValueError as e:
        error_code = str(e)
        if error_code == "NO_COMPLETED_RECORDINGS":
            raise HTTPException(
                status_code=400,
                detail={"error": "BAD_REQUEST", "message": "완료된 녹음이 없습니다."},
            )
        if error_code == "TRANSCRIPTION_IN_PROGRESS":
            raise HTTPException(
                status_code=409,
                detail={"error": "CONFLICT", "message": "이미 STT 변환이 진행 중입니다."},
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": str(e)},
        )
    except Exception as e:
        logger.exception(f"Failed to start transcription: meeting={meeting.id}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": f"STT 변환 시작에 실패했습니다: {str(e)}"},
        )


@router.get("/{meeting_id}/transcript/status", response_model=TranscriptStatusResponse)
async def get_transcription_status(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    transcript_service: Annotated[TranscriptService, Depends(get_transcript_service)],
):
    """STT 변환 진행 상태 조회

    회의의 STT 변환 진행 상태를 조회합니다.
    """
    try:
        status_info = await transcript_service.get_transcription_status(meeting.id)

        if not status_info:
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "트랜스크립트를 찾을 수 없습니다."},
            )

        return TranscriptStatusResponse(
            transcript_id=status_info["transcript_id"],
            status=status_info["status"],
            total_recordings=status_info["total_recordings"],
            processed_recordings=status_info["processed_recordings"],
            error=status_info.get("error"),
        )

    except ValueError as e:
        error_code = str(e)
        if error_code == "TRANSCRIPT_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "트랜스크립트를 찾을 수 없습니다."},
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "회의를 찾을 수 없습니다."},
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": str(e)},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get transcription status: meeting={meeting.id}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": f"상태 조회에 실패했습니다: {str(e)}"},
        )


@router.get("/{meeting_id}/transcript", response_model=MeetingTranscriptResponse)
async def get_meeting_transcript(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    transcript_service: Annotated[TranscriptService, Depends(get_transcript_service)],
):
    """회의 트랜스크립트 조회

    회의의 전체 트랜스크립트(화자별 병합 결과)를 조회합니다.
    STT 변환이 완료된 후에만 결과가 포함됩니다.
    """
    try:
        transcript = await transcript_service.get_transcript(meeting.id)

        if not transcript:
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "트랜스크립트를 찾을 수 없습니다."},
            )

        # utterances 변환 (DB에는 camelCase로 저장됨)
        utterances = None
        if transcript.utterances:
            from datetime import datetime
            utterances = [
                UtteranceResponse(
                    id=u["id"],
                    speaker_id=u["speakerId"],
                    speaker_name=u["speakerName"],
                    start_ms=u["startMs"],
                    end_ms=u["endMs"],
                    text=u["text"],
                    timestamp=datetime.fromisoformat(u["timestamp"]),
                )
                for u in transcript.utterances
            ]

        return MeetingTranscriptResponse(
            id=transcript.id,
            meeting_id=transcript.meeting_id,
            status=transcript.status,
            full_text=transcript.full_text,
            utterances=utterances,
            total_duration_ms=transcript.total_duration_ms,
            speaker_count=transcript.speaker_count,
            meeting_start=transcript.meeting_start,
            meeting_end=transcript.meeting_end,
            file_path=transcript.file_path,
            created_at=transcript.created_at,
            updated_at=transcript.updated_at,
            error=transcript.error,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get transcript: meeting={meeting.id}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": f"트랜스크립트 조회에 실패했습니다: {str(e)}"},
        )


@router.get("/{meeting_id}/transcript/download", response_model=TranscriptDownloadResponse)
async def get_transcript_download_url(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    transcript_service: Annotated[TranscriptService, Depends(get_transcript_service)],
):
    """회의록 다운로드 URL 조회

    MinIO에 저장된 회의록 JSON 파일의 Presigned URL을 반환합니다.
    URL은 1시간 동안 유효합니다.
    """
    try:
        transcript = await transcript_service.get_transcript(meeting.id)

        if not transcript:
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "트랜스크립트를 찾을 수 없습니다."},
            )

        if not transcript.file_path:
            raise HTTPException(
                status_code=400,
                detail={"error": "BAD_REQUEST", "message": "회의록 파일이 아직 생성되지 않았습니다."},
            )

        # Presigned URL 생성
        download_url = storage_service.get_transcript_url(transcript.file_path)

        return TranscriptDownloadResponse(
            meeting_id=meeting.id,
            download_url=download_url,
            expires_in_seconds=3600,  # 1시간
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get transcript download URL: meeting={meeting.id}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": f"다운로드 URL 생성에 실패했습니다: {str(e)}"},
        )
