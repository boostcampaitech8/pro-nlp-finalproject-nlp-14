"""Action Item Query Tools

Query tools for action item operations.
"""

import logging
from typing import Annotated

from app.core.neo4j import get_neo4j_driver
from app.repositories.kg.repository import KGRepository

from langchain_core.tools import InjectedToolArg

from ..decorators import ToolMode, mit_tool

logger = logging.getLogger(__name__)


@mit_tool(category="query", modes=[ToolMode.SPOTLIGHT])
async def get_my_action_items(
    status: str = "",
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """나에게 할당된 액션 아이템 목록을 조회합니다. status로 필터링 가능합니다. (예: 'pending', 'completed')"""
    logger.info(f"Executing get_my_action_items for user {_user_id}")

    driver = get_neo4j_driver()
    repo = KGRepository(driver)

    try:
        normalized_status = status or None
        action_items = await repo.get_action_items(
            user_id=str(_user_id),
            status=normalized_status,
        )
        return {
            "action_items": [
                {
                    "id": ai.id,
                    "content": ai.content,
                    "status": ai.status,
                    "due_date": ai.due_date.isoformat() if ai.due_date else None,
                    "decision_id": ai.decision_id,
                }
                for ai in action_items
            ],
            "count": len(action_items),
        }
    except Exception as e:
        logger.error(f"Failed to get action items: {e}", exc_info=True)
        return {"error": str(e)}
