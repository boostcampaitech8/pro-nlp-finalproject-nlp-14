import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_arq_pool, get_current_user
from app.core.database import get_db
from app.core.neo4j_sync import neo4j_sync
from app.models.meeting import Meeting, MeetingStatus
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.meeting import (
    CreateMeetingRequest,
    MeetingListResponse,
    MeetingResponse,
    MeetingWithParticipantsResponse,
    UpdateMeetingRequest,
)
from app.services.meeting_service import MeetingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Meetings"])
def get_meeting_service(db: Annotated[AsyncSession, Depends(get_db)]) -> MeetingService:
    """MeetingService 의존성"""
    return MeetingService(db)
# /api/v1/teams/{team_id}/meetings 엔드포인트
team_meetings_router = APIRouter(prefix="/teams/{team_id}/meetings", tags=["Meetings"])
@team_meetings_router.post(
    "",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_meeting(
    team_id: UUID,
    data: CreateMeetingRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> MeetingResponse:
    """회의 생성"""
    try:
        return await meeting_service.create_meeting(team_id, data, current_user.id)
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
@team_meetings_router.get(
    "",
    response_model=MeetingListResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def list_team_meetings(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
) -> MeetingListResponse:
    """팀 회의 목록"""
    try:
        return await meeting_service.list_team_meetings(
            team_id, current_user.id, page, limit, status
        )
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
# /api/v1/meetings/{meeting_id} 엔드포인트
@router.get(
    "/meetings/{meeting_id}",
    response_model=MeetingWithParticipantsResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_meeting(
    meeting_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> MeetingWithParticipantsResponse:
    """회의 상세 조회"""
    try:
        return await meeting_service.get_meeting(meeting_id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_TEAM_MEMBER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Not a team member"},
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )
@router.put(
    "/meetings/{meeting_id}",
    response_model=MeetingResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_meeting(
    meeting_id: UUID,
    data: UpdateMeetingRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> MeetingResponse:
    """회의 수정"""
    try:
        return await meeting_service.update_meeting(meeting_id, data, current_user.id)
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
                detail={"error": "FORBIDDEN", "message": "No permission to update meeting"},
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )
@router.delete(
    "/meetings/{meeting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_meeting(
    meeting_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    meeting_service: Annotated[MeetingService, Depends(get_meeting_service)],
) -> None:
    """회의 삭제"""
    try:
        await meeting_service.delete_meeting(meeting_id, current_user.id)
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
                detail={"error": "FORBIDDEN", "message": "No permission to delete meeting"},
            )
        if error_code == "MEETING_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Meeting not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)},
        )


@router.post(
    "/meetings/{meeting_id}/complete",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def complete_meeting_by_worker(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Worker가 회의 완료 요청 (모든 참여자 퇴장 시)"""
    # Meeting 조회
    query = select(Meeting).where(Meeting.id == meeting_id)
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # 멱등성 체크
    if meeting.status == MeetingStatus.COMPLETED.value:
        logger.info(f"Meeting already completed: {meeting_id}")
        return {"status": "already_completed"}

    # Meeting 상태 변경
    now = datetime.now(timezone.utc)
    meeting.status = MeetingStatus.COMPLETED.value
    meeting.ended_at = now
    await db.commit()
    await db.refresh(meeting)

    # Neo4j 동기화
    await neo4j_sync.sync_meeting_update(
        str(meeting.id),
        str(meeting.team_id),
        meeting.title,
        meeting.status,
        meeting.created_at,
    )

    # PR 생성 태스크 큐잉 (Worker가 transcript 유무를 확인)
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "generate_pr_task",
            str(meeting.id),
            _job_id=f"generate_pr:{meeting.id}",
        )
        await pool.close()
        logger.info(f"PR generation task queued: meeting={meeting.id}")
    except Exception as e:
        logger.error(f"Failed to enqueue PR task: {e}")

    # Job 삭제는 room_finished 웹훅에서 처리
    return {"status": "completed", "meeting_id": str(meeting.id)}
