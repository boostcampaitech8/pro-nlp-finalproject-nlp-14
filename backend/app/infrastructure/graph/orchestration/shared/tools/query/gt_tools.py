"""Ground Truth Query Tools

Query tools for retrieving confirmed decisions (Ground Truth).
"""

import logging
from typing import Annotated

from app.core.neo4j import get_neo4j_driver
from app.repositories.kg.repository import KGRepository

from langchain_core.tools import InjectedToolArg

from ..decorators import mit_tool

logger = logging.getLogger(__name__)


@mit_tool(category="query")
async def get_ground_truth(
    team_id: str,
    *,
    _user_id: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """팀의 Ground Truth(확정된 결정사항)를 조회합니다. 모든 회의에서 최종 확정(latest)된 Decision 목록을 반환합니다."""
    logger.info(f"Executing get_ground_truth for team {team_id}, user {_user_id}")

    if not team_id:
        return {"error": "team_id is required"}

    driver = get_neo4j_driver()
    repo = KGRepository(driver)

    try:
        decisions = await repo.get_team_latest_decisions(team_id=team_id)
        return {
            "decisions": decisions,
            "count": len(decisions),
        }
    except Exception as e:
        logger.error(f"Failed to get ground truth: {e}", exc_info=True)
        return {"error": str(e)}
