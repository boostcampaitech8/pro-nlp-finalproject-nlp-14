"""Meeting Mutation Tools

Mutation tools for meeting-related write operations.
These require HITL confirmation in Spotlight mode.
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from app.core.database import async_session_maker
from app.models.team import Team
from app.schemas.meeting import CreateMeetingRequest, UpdateMeetingRequest
from app.services.meeting_service import MeetingService

from langchain_core.tools import InjectedToolArg

from ..decorators import mit_tool

logger = logging.getLogger(__name__)


@mit_tool(
    category="mutation",
    display_template="{{team_id}} 팀에 '{{title}}' 회의를 {{scheduled_at}}에 만들까요?",
    hitl_fields={
        "team_id": {
            "input_type": "select",
            "options_source": "user_teams",
            "display_field": "name",
            "placeholder": "팀을 선택하세요",
        },
        "title": {
            "input_type": "text",
            "placeholder": "회의 제목을 입력하세요",
        },
        "scheduled_at": {
            "input_type": "datetime",
            "placeholder": "회의 일시를 선택하세요",
        },
        "description": {
            "input_type": "textarea",
            "placeholder": "회의 설명을 입력하세요 (선택사항)",
        },
    },
)
async def create_meeting(
    team_id: str,
    title: str,
    scheduled_at: str,
    description: str | None = None,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",  # Injected by tools.py
) -> dict:
    """새로운 회의를 생성합니다"""
    logger.info(f"Executing create_meeting for user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}
    if not title:
        return {"error": "title is required"}
    if not scheduled_at:
        return {"error": "scheduled_at is required"}

    try:
        team_uuid = UUID(str(team_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    # Parse datetime if string
    parsed_scheduled_at = scheduled_at
    if isinstance(scheduled_at, str):
        try:
            parsed_scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            return {"error": f"Invalid datetime format: {scheduled_at}"}

    async with async_session_maker() as db:
        service = MeetingService(db)
        try:
            # 팀 이름 조회
            team = await db.get(Team, team_uuid)
            team_name = team.name if team else "팀"

            request = CreateMeetingRequest(
                title=title,
                scheduled_at=parsed_scheduled_at,
                description=description,
            )
            result = await service.create_meeting(
                team_id=team_uuid,
                data=request,
                user_id=user_uuid,
            )
            await db.commit()
            return {
                "success": True,
                "meeting": result.model_dump(mode="json"),
                "message": f"'{team_name}' 팀에 '{result.title}' 회의가 생성되었습니다.",
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(
    category="mutation",
    display_template="회의 정보를 수정할까요?",
    hitl_fields={
        "meeting_id": {
            "input_type": "text",
            "placeholder": "회의 ID",
        },
        "title": {
            "input_type": "text",
            "placeholder": "새로운 회의 제목",
        },
        "scheduled_at": {
            "input_type": "datetime",
            "placeholder": "새로운 회의 일시",
        },
    },
)
async def update_meeting(
    meeting_id: str,
    title: str | None = None,
    scheduled_at: str | None = None,
    description: str | None = None,
    status: str | None = None,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """기존 회의의 정보를 수정합니다"""
    logger.info(f"Executing update_meeting for user {_user_id}")

    if not meeting_id:
        return {"error": "meeting_id is required"}

    try:
        meeting_uuid = UUID(str(meeting_id))
        user_uuid = UUID(str(_user_id))
    except ValueError as e:
        return {"error": f"Invalid UUID format: {e}"}

    # Parse datetime if string
    parsed_scheduled_at = None
    if scheduled_at and isinstance(scheduled_at, str):
        try:
            parsed_scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            return {"error": f"Invalid datetime format: {scheduled_at}"}

    async with async_session_maker() as db:
        service = MeetingService(db)
        try:
            request = UpdateMeetingRequest(
                title=title,
                scheduled_at=parsed_scheduled_at,
                description=description,
                status=status,
            )
            result = await service.update_meeting(
                meeting_id=meeting_uuid,
                data=request,
                user_id=user_uuid,
            )
            await db.commit()
            return {
                "success": True,
                "meeting": result.model_dump(mode="json"),
                "message": "회의 정보가 수정되었습니다.",
            }
        except ValueError as e:
            return {"error": str(e)}


@mit_tool(
    category="mutation",
    display_template="이 회의를 삭제할까요?",
    hitl_fields={
        "meeting_id": {
            "input_type": "text",
            "placeholder": "삭제할 회의 ID",
        },
    },
)
async def delete_meeting(
    meeting_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """회의를 삭제합니다"""
    logger.info(f"Executing delete_meeting for user {_user_id}")

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
            await service.delete_meeting(
                meeting_id=meeting_uuid,
                user_id=user_uuid,
            )
            await db.commit()
            return {
                "success": True,
                "message": "회의가 삭제되었습니다.",
            }
        except ValueError as e:
            return {"error": str(e)}
