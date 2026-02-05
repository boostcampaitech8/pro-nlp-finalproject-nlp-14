"""Meeting Query Tools

Query tools for meeting-related read operations.
"""

import logging
from uuid import UUID

from app.core.database import async_session_maker
from app.services.meeting_service import MeetingService

from ..decorators import mit_tool

logger = logging.getLogger(__name__)


@mit_tool(category="query")
async def get_meetings(
    team_id: str,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
    *,
    _user_id: str = "",
) -> dict:
    """팀의 회의 목록을 조회합니다. 상태별 필터링이 가능합니다."""
    logger.info(f"Executing get_meetings for user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}

    try:
        team_uuid = UUID(str(team_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = MeetingService(db)
        try:
            result = await service.list_team_meetings(
                team_id=team_uuid,
                user_id=user_uuid,
                page=page,
                limit=limit,
                status=status,
            )
            return {
                "meetings": [m.model_dump(mode="json") for m in result.items],
                "meta": result.meta.model_dump(),
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(category="query")
async def get_meeting(
    meeting_id: str,
    *,
    _user_id: str = "",
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
