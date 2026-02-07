"""Voice-specific Query Tools

Query tools available only in Voice mode.
"""

import logging
from typing import Annotated
from uuid import UUID

from app.core.database import async_session_maker
from app.services.meeting_service import MeetingService
from app.services.team_service import TeamService

from langchain_core.tools import InjectedToolArg

from ..decorators import ToolMode, mit_tool

logger = logging.getLogger(__name__)


@mit_tool(category="query", modes=[ToolMode.VOICE])
async def get_team_by_meeting_id(
    meeting_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """현재 회의가 속한 팀의 정보를 조회합니다."""
    logger.info(f"Executing get_team_by_meeting_id for user {_user_id}")

    if not meeting_id:
        return {"error": "meeting_id is required"}

    try:
        meeting_uuid = UUID(str(meeting_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        meeting_service = MeetingService(db)
        team_service = TeamService(db)
        try:
            meeting = await meeting_service.get_meeting(
                meeting_id=meeting_uuid,
                user_id=user_uuid,
            )
            team = await team_service.get_team(
                team_id=meeting.team_id,
                user_id=user_uuid,
            )
            return {"team": team.model_dump(mode="json")}
        except ValueError as e:
            return {"error": str(e)}
