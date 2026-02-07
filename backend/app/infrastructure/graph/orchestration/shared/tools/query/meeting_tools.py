"""Meeting Query Tools

Query tools for meeting-related read operations.
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.database import async_session_maker
from app.services.meeting_service import MeetingService

from langchain_core.tools import InjectedToolArg

from ..decorators import mit_tool

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


@mit_tool(category="query")
async def get_meetings(
    team_id: str,
    status: str = "",
    time_filter: str = "",
    page: int = 1,
    limit: int = 20,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀의 회의 목록을 조회합니다. 상태별, 시간별 필터링이 가능합니다.
    time_filter: 'future'(예정된 회의), 'past'(지난 회의), ''(전체)"""
    logger.info(f"Executing get_meetings for user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}

    try:
        team_uuid = UUID(str(team_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    normalized_status = status or None

    async with async_session_maker() as db:
        service = MeetingService(db)
        try:
            result = await service.list_team_meetings(
                team_id=team_uuid,
                user_id=user_uuid,
                page=page,
                limit=limit,
                status=normalized_status,
            )

            meetings = [m.model_dump(mode="json") for m in result.items]

            # time_filter 적용
            if time_filter:
                now = datetime.now(KST)
                filtered = []
                for m in meetings:
                    scheduled_at = m.get("scheduled_at")
                    if not scheduled_at:
                        continue
                    if isinstance(scheduled_at, str):
                        try:
                            meeting_time = datetime.fromisoformat(scheduled_at)
                        except ValueError:
                            continue
                    else:
                        meeting_time = scheduled_at

                    if time_filter == "future" and meeting_time >= now:
                        filtered.append(m)
                    elif time_filter == "past" and meeting_time < now:
                        filtered.append(m)
                meetings = filtered

            return {
                "meetings": meetings,
                "meta": result.meta.model_dump(),
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(category="query")
async def get_meeting(
    meeting_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """회의의 상세 정보를 조회합니다. 참여자 목록이 포함됩니다."""
    logger.info(f"Executing get_meeting for user {_user_id}")

    if not meeting_id:
        return {"error": "meeting_id is required"}

    try:
        meeting_uuid = UUID(str(meeting_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = MeetingService(db)
        try:
            result = await service.get_meeting(
                meeting_id=meeting_uuid,
                user_id=user_uuid,
            )
            return {"meeting": result.model_dump(mode="json")}
        except ValueError as e:
            return {"error": str(e)}
