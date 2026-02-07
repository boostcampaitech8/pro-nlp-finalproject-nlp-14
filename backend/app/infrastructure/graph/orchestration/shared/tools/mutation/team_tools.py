"""Team Mutation Tools

Mutation tools for team-related write operations.
These require HITL confirmation in Spotlight mode.
"""

import logging
from typing import Annotated
from uuid import UUID

from app.core.database import async_session_maker
from app.schemas.team import CreateTeamRequest, UpdateTeamRequest
from app.schemas.team_member import InviteTeamMemberRequest
from app.services.invite_link_service import InviteLinkService
from app.services.team_member_service import TeamMemberService
from app.services.team_service import TeamService

from langchain_core.tools import InjectedToolArg

from ..decorators import ToolMode, mit_tool

logger = logging.getLogger(__name__)


@mit_tool(
    category="mutation",
    modes=[ToolMode.SPOTLIGHT],
    display_template="'{{name}}' 팀을 만들까요?",
    hitl_fields={
        "name": {
            "input_type": "text",
            "placeholder": "팀 이름",
        },
        "description": {
            "input_type": "textarea",
            "placeholder": "팀 설명 (선택)",
        },
    },
)
async def create_team(
    name: str,
    description: str | None = None,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """새로운 팀을 생성합니다

    Args:
        name: 팀 이름
        description: 팀 설명 (선택사항)
    """
    logger.info(f"Executing create_team for user {_user_id}")

    if not name:
        return {"error": "name is required"}

    try:
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = TeamService(db)
        try:
            request = CreateTeamRequest(
                name=name,
                description=description,
            )
            result = await service.create_team(
                data=request,
                user_id=user_uuid,
            )
            await db.commit()
            return {
                "success": True,
                "team": result.model_dump(mode="json"),
                "message": f"'{result.name}' 팀이 생성되었습니다.",
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(
    category="mutation",
    modes=[ToolMode.SPOTLIGHT],
    display_template="팀 정보를 수정할까요?",
    hitl_fields={
        "team_id": {
            "input_type": "select",
            "options_source": "user_teams",
            "display_field": "name",
            "placeholder": "팀을 선택하세요",
        },
        "name": {
            "input_type": "text",
            "placeholder": "새로운 팀 이름",
        },
        "description": {
            "input_type": "textarea",
            "placeholder": "새로운 팀 설명",
        },
    },
)
async def update_team(
    team_id: str,
    name: str | None = None,
    description: str | None = None,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀의 이름이나 설명을 수정합니다.

    Args:
        team_id: 수정할 팀의 UUID (예: 'a5aed891-35e3-4678-903b-44f0b13742b0'). 반드시 사용자의 팀 목록에서 id 값을 사용해야 합니다.
        name: 새로운 팀 이름 (선택사항)
        description: 새로운 팀 설명 (선택사항)
    """
    logger.info(f"Executing update_team for user {_user_id}")

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
            request = UpdateTeamRequest(
                name=name,
                description=description,
            )
            result = await service.update_team(
                team_id=team_uuid,
                data=request,
                user_id=user_uuid,
            )
            await db.commit()
            return {
                "success": True,
                "team": result.model_dump(mode="json"),
                "message": "팀 정보가 수정되었습니다.",
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(
    category="mutation",
    modes=[ToolMode.SPOTLIGHT],
    display_template="'{{team_id}}' 팀을 삭제할까요?",
    hitl_fields={
        "team_id": {
            "input_type": "select",
            "options_source": "user_teams",
            "display_field": "name",
            "placeholder": "삭제할 팀을 선택하세요",
        },
    },
)
async def delete_team(
    team_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀을 삭제합니다. 팀 소유자만 가능합니다.

    Args:
        team_id: 삭제할 팀의 UUID (예: 'a5aed891-35e3-4678-903b-44f0b13742b0'). 반드시 사용자의 팀 목록에서 id 값을 사용해야 합니다.
    """
    logger.info(f"Executing delete_team for user {_user_id}")

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
            await service.delete_team(
                team_id=team_uuid,
                user_id=user_uuid,
            )
            await db.commit()
            return {
                "success": True,
                "message": "팀이 삭제되었습니다.",
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(
    category="mutation",
    modes=[ToolMode.SPOTLIGHT],
    display_template="{{email}}을 팀에 초대할까요?",
    hitl_fields={
        "team_id": {
            "input_type": "select",
            "options_source": "user_teams",
            "display_field": "name",
            "placeholder": "팀을 선택하세요",
        },
        "email": {
            "input_type": "text",
            "placeholder": "초대할 이메일",
        },
        "role": {
            "input_type": "select",
            "options": ["member", "admin"],
            "placeholder": "역할을 선택하세요",
        },
    },
)
async def invite_team_member(
    team_id: str,
    email: str,
    role: str = "member",
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀에 새 멤버를 초대합니다.

    Args:
        team_id: 멤버를 초대할 팀의 UUID (예: 'a5aed891-35e3-4678-903b-44f0b13742b0'). 반드시 사용자의 팀 목록에서 id 값을 사용해야 합니다.
        email: 초대할 사용자의 이메일 주소
        role: 팀 내 역할 ('member' 또는 'admin', 기본값: 'member')
    """
    logger.info(f"Executing invite_team_member for user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}
    if not email:
        return {"error": "email is required"}

    try:
        team_uuid = UUID(str(team_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = TeamMemberService(db)
        try:
            request = InviteTeamMemberRequest(
                email=email,
                role=role,
            )
            result = await service.invite_member(
                team_id=team_uuid,
                data=request,
                current_user_id=user_uuid,
            )
            await db.commit()
            return {
                "success": True,
                "member": result.model_dump(mode="json"),
                "message": f"{email}을 팀에 초대했습니다.",
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(
    category="mutation",
    modes=[ToolMode.SPOTLIGHT],
    display_template="{{team_id}} 팀 초대 링크를 발급할까요?",
    hitl_fields={
        "team_id": {
            "input_type": "select",
            "options_source": "user_teams",
            "display_field": "name",
            "placeholder": "팀을 선택하세요",
        },
    },
)
async def generate_team_invite_link(
    team_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀 초대 링크를 생성합니다. 기존 링크가 있으면 새 링크로 교체됩니다.

    Args:
        team_id: 초대 링크를 생성할 팀의 UUID (예: 'a5aed891-35e3-4678-903b-44f0b13742b0'). 반드시 사용자의 팀 목록에서 id 값을 사용해야 합니다.
    """
    logger.info(f"Executing generate_team_invite_link for user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}

    try:
        team_uuid = UUID(str(team_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    async with async_session_maker() as db:
        service = InviteLinkService(db)
        try:
            result = await service.generate_invite_link(
                team_id=team_uuid,
                current_user_id=user_uuid,
            )
            return {
                "success": True,
                "invite_link": result.model_dump(mode="json", by_alias=True),
                "message": f"팀 초대 링크를 발급했습니다: {result.invite_url}",
            }
        except ValueError as e:
            return {"error": str(e)}
