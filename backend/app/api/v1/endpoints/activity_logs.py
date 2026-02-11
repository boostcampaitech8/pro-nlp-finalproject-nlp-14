"""사용자 활동 로그 API 엔드포인트"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.telemetry import get_mit_metrics
from app.models.user_activity_log import UserActivityLog

logger = logging.getLogger(__name__)

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

    mit_metrics = get_mit_metrics()
    for event in data.events:
        logger.info(
            "activity_log | session=%s | event_type=%s | page_path=%s | user_id=%s | target=%s",
            data.session_id,
            event.event_type,
            event.page_path,
            data.user_id or "anonymous",
            event.event_target or "",
        )
        if mit_metrics:
            mit_metrics.activity_events_total.add(
                1,
                {"event_type": event.event_type, "page_path": event.page_path},
            )

    return {"message": f"Created {len(logs)} activity logs", "count": len(logs)}
