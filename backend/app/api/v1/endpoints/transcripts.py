"""Transcript API 엔드포인트 (실시간 STT)"""

import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_arq_pool, require_meeting_participant
from app.core.constants import AGENT_USER_ID
from app.core.database import get_db
from app.core.telemetry import get_mit_metrics
from app.models.meeting import Meeting
from app.schemas.transcript import (
    CreateTranscriptRequest,
    CreateTranscriptResponse,
    GetMeetingTranscriptsResponse,
)
from app.services.context_runtime import (
    ContextRuntimeState,
    get_runtime_if_exists,
    update_runtime_from_db,
)
from app.services.transcript_service import TranscriptService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["Transcripts"])


def get_transcript_service(db: Annotated[AsyncSession, Depends(get_db)]) -> TranscriptService:
    """TranscriptService 의존성"""
    return TranscriptService(db)


def _serialize_runtime_topics(runtime: ContextRuntimeState) -> list[dict]:
    """ARQ payload 전달용 L1 토픽 스냅샷 직렬화."""
    topics = [
        {
            "id": seg.id,
            "name": seg.name,
            "summary": seg.summary,
            "startTurn": seg.start_utterance_id,
            "endTurn": seg.end_utterance_id,
            "keywords": seg.keywords,
        }
        for seg in runtime.manager.get_l1_segments()
    ]
    topics.sort(key=lambda topic: topic["startTurn"])
    return topics


@router.post(
    "/{meeting_id}/transcripts",
    response_model=CreateTranscriptResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid request"},
        404: {"description": "Meeting not found"},
    },
)
async def create_transcript(
    meeting_id: UUID,
    request: CreateTranscriptRequest,
    transcript_service: Annotated[TranscriptService, Depends(get_transcript_service)],
) -> CreateTranscriptResponse:
    """발화 segment 저장 (Worker → Backend)

    Worker가 전송한 전사 segment를 DB에 저장합니다.

    Args:
        meeting_id: 회의 ID (path parameter)
        request: 발화 segment 데이터
        transcript_service: TranscriptService 의존성

    Returns:
        CreateTranscriptResponse: 생성된 segment ID와 생성 시간

    Raises:
        HTTPException:
            - 400: path meeting_id와 body meetingId 불일치, startMs/endMs 유효하지 않음
            - 403: system user ID 사용 시도
            - 404: meeting 존재하지 않음
    """
    # System user ID 사용 차단 (agent endpoint에서만 사용 가능)
    if request.user_id == AGENT_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "FORBIDDEN_USER_ID",
                "message": "System user ID는 사용할 수 없습니다.",
            },
        )

    try:
        return await transcript_service.create_transcript(meeting_id, request)
    except ValueError as e:
        error_code = str(e)
        if error_code == "MEETING_ID_MISMATCH":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "MEETING_ID_MISMATCH",
                    "message": "Path meeting_id와 body meetingId가 일치하지 않습니다.",
                },
            )
        if error_code == "INVALID_TIME_RANGE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_TIME_RANGE",
                    "message": "endMs는 startMs보다 커야 합니다.",
                },
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "MEETING_NOT_FOUND",
                    "message": "회의를 찾을 수 없습니다.",
                },
            )
        # 예상치 못한 에러
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": str(e),
            },
        )


@router.get(
    "/{meeting_id}/transcripts",
    response_model=GetMeetingTranscriptsResponse,
    response_model_by_alias=True,
    responses={
        404: {"description": "Meeting not found"},
    },
)
async def get_meeting_transcripts(
    meeting_id: UUID,
    transcript_service: Annotated[TranscriptService, Depends(get_transcript_service)],
) -> GetMeetingTranscriptsResponse:
    """회의 전체 전사 조회 (Client → Backend)

    회의 ID를 기준으로 모든 전사 segment를 조회하고,
    시간 순서대로 정렬된 전체 전사 텍스트를 반환합니다.

    Args:
        meeting_id: 회의 ID (path parameter)
        transcript_service: TranscriptService 의존성

    Returns:
        GetMeetingTranscriptsResponse: 회의 전체 전사 데이터

    Raises:
        HTTPException:
            - 404: meeting 존재하지 않음
    """
    try:
        return await transcript_service.get_meeting_transcripts(meeting_id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "MEETING_NOT_FOUND",
                    "message": "회의를 찾을 수 없습니다.",
                },
            )
        # 예상치 못한 에러
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_ERROR",
                "message": str(e),
            },
        )


@router.post(
    "/{meeting_id}/generate-pr",
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_pr(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    transcript_service: Annotated[TranscriptService, Depends(get_transcript_service)],
):
    """회의록 PR 생성 시작

    회의 트랜스크립트를 기반으로 Agenda와 Decision을 추출합니다.
    실시간 STT 변환이 완료된 후에 호출해야 합니다.

    동일 회의에 대해 중복 호출 시 기존 작업이 있으면 무시됩니다.
    """
    try:
        # 트랜스크립트 존재 확인 (새 transcripts 테이블)
        transcript_response = await transcript_service.get_meeting_transcripts(meeting.id)

        if not transcript_response.full_text:
            raise HTTPException(
                status_code=404,
                detail={"error": "NOT_FOUND", "message": "트랜스크립트를 찾을 수 없습니다. 먼저 실시간 STT 변환을 완료해주세요."},
            )

        # 실시간 L1 토픽 스냅샷 추출 (best-effort)
        realtime_topics: list[dict] = []
        runtime = get_runtime_if_exists(str(meeting.id))
        if runtime is not None:
            async with runtime.lock:
                await update_runtime_from_db(
                    runtime=runtime,
                    db=transcript_service.db,
                    meeting_id=str(meeting.id),
                    cutoff_start_ms=None,
                )

            # L1이 진행 중이면 짧게 대기 후 현재 스냅샷 사용
            if runtime.manager.has_pending_l1 or runtime.manager.is_l1_running:
                try:
                    await asyncio.wait_for(runtime.manager.await_l1_idle(), timeout=6.0)
                except asyncio.TimeoutError:
                    logger.info(
                        "generate_pr 토픽 스냅샷 대기 타임아웃: meeting_id=%s",
                        meeting.id,
                    )

            async with runtime.lock:
                realtime_topics = _serialize_runtime_topics(runtime)

        logger.info(
            "generate_pr enqueue 준비: meeting_id=%s, realtime_topics=%d",
            meeting.id,
            len(realtime_topics),
        )

        # ARQ 작업 큐잉 (job_id로 중복 방지)
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "generate_pr_task",
            str(meeting.id),
            realtime_topics,
            _job_id=f"generate_pr:{meeting.id}",
        )
        await pool.close()

        # 메트릭 기록
        metrics = get_mit_metrics()
        if metrics:
            metrics.arq_task_enqueue_total.add(1, {"task_name": "generate_pr_task"})

        return {
            "status": "queued",
            "meeting_id": str(meeting.id),
            "job_id": f"generate_pr:{meeting.id}",
            "message": "PR 생성 작업이 시작되었습니다.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to start generate_pr: meeting={meeting.id}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": f"PR 생성 시작에 실패했습니다: {str(e)}"},
        )
