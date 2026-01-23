"""MCP 실행 노드"""

import logging

from app.infrastructure.graph.config import get_graph_settings
from app.infrastructure.graph.workflows.mit_action.state import (
    MitActionState,
)

logger = logging.getLogger(__name__)


async def execute_mcp(state: MitActionState) -> MitActionState:
    """MCP 도구로 외부 시스템에 Action Item 생성

    Contract:
        reads: mit_action_actions
        writes: mit_action_mcp_result
        side-effects: MCP 도구 호출 (Jira, Notion 등)
        failures: MCP_FAILED -> errors 기록

    NOTE: MCP 연동은 추후 구현. 현재는 스켈레톤만.
    """
    settings = get_graph_settings()

    if not settings.mcp_enabled:
        logger.info("MCP 비활성화 상태, 스킵")
        return MitActionState(mit_action_mcp_result=None)

    logger.info("MCP 실행 시작")

    actions = state.get("mit_action_actions", [])

    # TODO: MCP 도구 호출
    # 1. 연결된 MCP 도구 확인 (Jira, Notion 등)
    # 2. 각 Action Item에 대해 티켓/태스크 생성
    # 3. 결과 수집

    mcp_result = {
        "status": "skipped",
        "message": "MCP 연동 미구현 (스켈레톤)",
        "created_count": 0,
    }

    logger.info(f"MCP 실행 완료: {mcp_result}")

    return MitActionState(mit_action_mcp_result=mcp_result)
