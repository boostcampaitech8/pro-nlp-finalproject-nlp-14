"""Utility Query Tools

General utility tools for common queries:
- User profile
- Upcoming meetings
- Meeting transcript
- Meeting summary
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from langchain_core.tools import InjectedToolArg

from app.core.database import async_session_maker
from app.core.neo4j import get_neo4j_driver
from app.models.meeting import Meeting, MeetingStatus
from app.models.team import TeamMember
from app.models.user import User
from app.services.minutes_service import MinutesService
from app.services.transcript_service import TranscriptService

from ..decorators import mit_tool

logger = logging.getLogger(__name__)

# KST timezone
KST = ZoneInfo("Asia/Seoul")


@mit_tool(category="query")
async def get_user_profile(*, _user_id: Annotated[str, InjectedToolArg] = "") -> dict:
    """현재 사용자의 프로필 정보를 조회합니다. 이름, 이메일, 가입일 등을 확인할 수 있습니다."""
    logger.info(f"Executing get_user_profile for user {_user_id}")

    try:
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid user ID format: {e}"}

    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

        if not user:
            return {"error": "USER_NOT_FOUND"}

        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "auth_provider": user.auth_provider,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        }


@mit_tool(category="query")
async def get_upcoming_meetings(
    limit: int = 5,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """사용자가 속한 팀의 다가오는 회의 목록을 조회합니다. 예정된(scheduled) 또는 진행 중인(ongoing) 회의를 포함합니다.

    Args:
        limit: 조회할 회의 수 (기본값: 5, 최대: 20)
    """
    logger.info(f"Executing get_upcoming_meetings for user {_user_id}")

    try:
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid user ID format: {e}"}

    # Limit validation
    if not isinstance(limit, int) or limit < 1:
        limit = 5
    limit = min(limit, 20)  # Max 20

    now = datetime.now(KST)

    async with async_session_maker() as db:
        # 1. 사용자가 속한 팀 ID 조회
        team_result = await db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user_uuid)
        )
        team_ids = [row[0] for row in team_result.all()]

        if not team_ids:
            return {
                "meetings": [],
                "count": 0,
                "message": "사용자가 속한 팀이 없습니다.",
            }

        # 2. 해당 팀들의 예정된/진행중인 회의 조회
        meetings_result = await db.execute(
            select(Meeting)
            .options(selectinload(Meeting.team))
            .where(
                Meeting.team_id.in_(team_ids),
                Meeting.status.in_(
                    [MeetingStatus.SCHEDULED.value, MeetingStatus.ONGOING.value]
                ),
                Meeting.scheduled_at >= now,
            )
            .order_by(Meeting.scheduled_at.asc())
            .limit(limit)
        )
        meetings = meetings_result.scalars().all()

        return {
            "meetings": [
                {
                    "id": str(m.id),
                    "title": m.title,
                    "description": m.description,
                    "status": m.status,
                    "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
                    "team": {
                        "id": str(m.team.id),
                        "name": m.team.name,
                    } if m.team else None,
                }
                for m in meetings
            ],
            "count": len(meetings),
        }


@mit_tool(category="query")
async def get_meeting_transcript(
    meeting_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """회의의 전체 전사 기록을 조회합니다. 발화 내용, 발화자, 시간 정보가 포함됩니다.

    Args:
        meeting_id: 전사 기록을 조회할 회의의 UUID (예: 'a5aed891-35e3-4678-903b-44f0b13742b0')
    """
    logger.info(f"Executing get_meeting_transcript for user {_user_id}")

    if not meeting_id:
        return {"error": "meeting_id is required"}

    try:
        meeting_uuid = UUID(str(meeting_id))
    except ValueError as e:
        return {"error": f"Invalid meeting_id format: {e}"}

    async with async_session_maker() as db:
        service = TranscriptService(db)
        try:
            result = await service.get_meeting_transcripts(meeting_uuid)
            return {
                "transcript": {
                    "meeting_id": str(result.meeting_id),
                    "status": result.status,
                    "full_text": result.full_text,
                    "utterances": [
                        {
                            "id": str(u.id),
                            "speaker_id": str(u.speaker_id),
                            "speaker_name": u.speaker_name,
                            "text": u.text,
                            "start_ms": u.start_ms,
                            "end_ms": u.end_ms,
                            "timestamp": u.timestamp.isoformat() if u.timestamp else None,
                        }
                        for u in result.utterances
                    ],
                    "total_duration_ms": result.total_duration_ms,
                    "speaker_count": result.speaker_count,
                }
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(category="query")
async def get_meeting_summary(
    meeting_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """회의의 요약, 안건(Agenda), 결정 사항(Decision), 액션 아이템(Action Item)을 조회합니다.

    Args:
        meeting_id: 요약을 조회할 회의의 UUID (예: 'a5aed891-35e3-4678-903b-44f0b13742b0')
    """
    logger.info(f"Executing get_meeting_summary for user {_user_id}")

    if not meeting_id:
        return {"error": "meeting_id is required"}

    try:
        # Validate UUID format
        UUID(str(meeting_id))
    except ValueError as e:
        return {"error": f"Invalid meeting_id format: {e}"}

    driver = get_neo4j_driver()
    service = MinutesService(driver)

    try:
        result = await service.get_minutes(str(meeting_id))
        return {
            "summary": {
                "meeting_id": result.meeting_id,
                "summary": result.summary,
                "agendas": [
                    {
                        "id": a.id,
                        "topic": a.topic,
                        "description": a.description,
                        "order": a.order,
                        "decisions": [
                            {
                                "id": d.id,
                                "content": d.content,
                                "status": d.status,
                            }
                            for d in a.decisions
                        ],
                    }
                    for a in result.agendas
                ],
                "action_items": [
                    {
                        "id": ai.id,
                        "content": ai.content,
                        "status": ai.status,
                        "assignee_id": ai.assignee_id,
                        "due_date": ai.due_date.isoformat() if ai.due_date else None,
                    }
                    for ai in result.action_items
                ],
            }
        }
    except ValueError as e:
        return {"error": str(e)}
