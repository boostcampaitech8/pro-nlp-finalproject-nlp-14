"""사용자 활동 로그 API 엔드포인트"""

import csv
import io
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.user_activity_log import UserActivityLog

router = APIRouter(prefix="/logs", tags=["Activity Logs"])


class ActivityEventInput(BaseModel):
    """단일 활동 이벤트 입력"""
    event_type: str = Field(..., max_length=32)
    event_target: str | None = Field(None, max_length=512)
    page_path: str = Field(..., max_length=255)
    metadata: dict | None = None
    timestamp: datetime


class ActivityLogBatchInput(BaseModel):
    """활동 로그 배치 입력"""
    session_id: str = Field(..., max_length=64)
    user_id: str | None = Field(None, description="로그인된 사용자 ID (JWT에서 추출)")
    events: list[ActivityEventInput] = Field(..., max_length=100)


class ActivityLogResponse(BaseModel):
    """활동 로그 응답"""
    id: int
    user_id: str | None
    session_id: str
    event_type: str
    event_target: str | None
    page_path: str
    metadata: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityLogsListResponse(BaseModel):
    """활동 로그 목록 응답"""
    logs: list[ActivityLogResponse]
    total: int
    page: int
    limit: int


@router.post("/activity", status_code=201)
async def create_activity_logs(
    request: Request,
    data: ActivityLogBatchInput,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """활동 로그 배치 저장

    프론트엔드에서 수집한 사용자 활동 이벤트를 배치로 저장합니다.
    """
    # Get user_id from request body (frontend extracts from JWT)
    user_id = UUID(data.user_id) if data.user_id else None

    # Get client info
    user_agent = request.headers.get("user-agent", "")[:512]
    ip_address = request.client.host if request.client else None

    logs = []
    for event in data.events:
        log = UserActivityLog(
            user_id=user_id,
            session_id=data.session_id,
            event_type=event.event_type,
            event_target=event.event_target,
            page_path=event.page_path,
            event_metadata=event.metadata,
            user_agent=user_agent,
            ip_address=ip_address,
            created_at=event.timestamp,
        )
        db.add(log)
        logs.append(log)

    await db.flush()

    return {"message": f"Created {len(logs)} activity logs", "count": len(logs)}


@router.get("/activity", response_model=ActivityLogsListResponse)
async def get_activity_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: datetime | None = Query(None, description="시작 날짜 (UTC)"),
    end_date: datetime | None = Query(None, description="종료 날짜 (UTC)"),
    event_type: str | None = Query(None, description="이벤트 타입 필터"),
    session_id: str | None = Query(None, description="세션 ID 필터"),
    page_path: str | None = Query(None, description="페이지 경로 필터"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """활동 로그 조회 (인증 필요)

    필터 조건에 맞는 활동 로그를 조회합니다.
    """
    query = select(UserActivityLog)
    count_query = select(func.count(UserActivityLog.id))

    # Apply filters
    if start_date:
        query = query.where(UserActivityLog.created_at >= start_date)
        count_query = count_query.where(UserActivityLog.created_at >= start_date)
    if end_date:
        query = query.where(UserActivityLog.created_at <= end_date)
        count_query = count_query.where(UserActivityLog.created_at <= end_date)
    if event_type:
        query = query.where(UserActivityLog.event_type == event_type)
        count_query = count_query.where(UserActivityLog.event_type == event_type)
    if session_id:
        query = query.where(UserActivityLog.session_id == session_id)
        count_query = count_query.where(UserActivityLog.session_id == session_id)
    if page_path:
        query = query.where(UserActivityLog.page_path.ilike(f"%{page_path}%"))
        count_query = count_query.where(UserActivityLog.page_path.ilike(f"%{page_path}%"))

    # Pagination
    query = query.order_by(UserActivityLog.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return ActivityLogsListResponse(
        logs=[
            ActivityLogResponse(
                id=log.id,
                user_id=str(log.user_id) if log.user_id else None,
                session_id=log.session_id,
                event_type=log.event_type,
                event_target=log.event_target,
                page_path=log.page_path,
                metadata=log.event_metadata,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/activity/export")
async def export_activity_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: datetime | None = Query(None, description="시작 날짜 (UTC)"),
    end_date: datetime | None = Query(None, description="종료 날짜 (UTC)"),
    event_type: str | None = Query(None, description="이벤트 타입 필터"),
):
    """활동 로그 CSV 내보내기 (인증 필요)

    필터 조건에 맞는 활동 로그를 CSV 파일로 내보냅니다.
    """
    query = select(UserActivityLog)

    if start_date:
        query = query.where(UserActivityLog.created_at >= start_date)
    if end_date:
        query = query.where(UserActivityLog.created_at <= end_date)
    if event_type:
        query = query.where(UserActivityLog.event_type == event_type)

    query = query.order_by(UserActivityLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "user_id", "session_id", "event_type",
        "event_target", "page_path", "metadata",
        "user_agent", "ip_address", "created_at"
    ])

    for log in logs:
        writer.writerow([
            log.id,
            str(log.user_id) if log.user_id else "",
            log.session_id,
            log.event_type,
            log.event_target or "",
            log.page_path,
            str(log.event_metadata) if log.event_metadata else "",
            log.user_agent or "",
            log.ip_address or "",
            log.created_at.isoformat(),
        ])

    output.seek(0)

    filename = f"activity_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
