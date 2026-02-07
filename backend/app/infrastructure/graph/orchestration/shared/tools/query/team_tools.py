"""Team Query Tools

Query tools for team-related read operations.
"""

import logging
from typing import Annotated
from uuid import UUID

from app.core.database import async_session_maker
from app.services.team_member_service import TeamMemberService
from app.services.team_service import TeamService

from langchain_core.tools import InjectedToolArg

from ..decorators import ToolMode, mit_tool

logger = logging.getLogger(__name__)


@mit_tool(category="query", modes=[ToolMode.SPOTLIGHT])
async def get_my_teams(
    page: int = 1,
    limit: int = 20,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """내가 속한 팀 목록을 조회합니다."""
    logger.info(f"Executing get_my_teams for user {_user_id}")

    try:
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = TeamService(db)
        try:
            result = await service.list_my_teams(
                user_id=user_uuid,
                page=page,
                limit=limit,
            )
            return {
                "teams": [t.model_dump(mode="json") for t in result.items],
                "meta": result.meta.model_dump(),
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(category="query")
async def get_team(
    team_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀의 상세 정보를 조회합니다. 멤버 목록이 포함됩니다."""
    logger.info(f"Executing get_team for user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}

    try:
        team_uuid = UUID(str(team_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = TeamService(db)
        try:
            result = await service.get_team(
                team_id=team_uuid,
                user_id=user_uuid,
            )
            return {"team": result.model_dump(mode="json")}
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(category="query", modes=[ToolMode.SPOTLIGHT])
async def get_team_members(
    team_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀의 멤버 목록을 조회합니다. 각 멤버의 이름, 이메일, 역할(owner/admin/member) 정보가 포함됩니다."""
    logger.info(f"Executing get_team_members for user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}

    try:
        team_uuid = UUID(str(team_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = TeamMemberService(db)
        try:
            members = await service.list_members(
                team_id=team_uuid,
                current_user_id=user_uuid,
            )
            return {
                "members": [
                    {
                        "id": str(m.id),
                        "user_id": str(m.user_id),
                        "name": m.user.name if m.user else None,
                        "email": m.user.email if m.user else None,
                        "role": m.role,
                        "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                    }
                    for m in members
                ],
                "count": len(members),
            }
        except ValueError as e:
            return {"error": str(e)}
