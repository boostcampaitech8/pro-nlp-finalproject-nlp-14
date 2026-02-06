"""Voice 단순화된 Tool Execution Node - Query 도구만, HITL 없음"""

import logging

from app.infrastructure.graph.orchestration.shared.tools.registry import get_tool_by_name

from ..state import VoiceOrchestrationState

logger = logging.getLogger(__name__)


async def execute_tools(state: VoiceOrchestrationState) -> VoiceOrchestrationState:
    """Voice 도구 실행 노드 (Query 도구만, HITL 없음)

    Voice 모드는 Query 도구만 사용하며 HITL이 필요 없음:
    - Mutation 도구는 Voice 모드에서 사용 불가
    - 사용자 확인 절차 없이 즉시 실행

    Contract:
        reads: selected_tool, tool_args, user_id
        writes: tool_results
        side-effects: Tool 실행 (DB/Neo4j 읽기 작업)
        failures: TOOL_NOT_FOUND, TOOL_EXECUTION_ERROR
    """
    logger.info("Voice Tool execution node entered")

    selected_tool = state.get("selected_tool")
    user_id = state.get("user_id")
    tool_args = state.get("tool_args", {})

    if not selected_tool:
        logger.warning("No tool selected")
        return VoiceOrchestrationState(
            tool_results="도구가 선택되지 않았습니다.",
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    # Get the tool
    tool = get_tool_by_name(selected_tool)
    if not tool:
        logger.error(f"Tool not found: {selected_tool}")
        return VoiceOrchestrationState(
            tool_results=f"'{selected_tool}' 도구를 찾을 수 없습니다.",
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    logger.info(f"Executing Query tool: {selected_tool}")

    # _user_id 인젝션
    if "_user_id" in tool.args:
        tool_args["_user_id"] = user_id

    try:
        # Voice는 Query 도구만 사용하므로 즉시 실행
        result = await tool.ainvoke(tool_args)
        logger.info(f"Tool [{selected_tool}] 실행 성공")
        logger.debug(f"Tool result: {str(result)[:200]}...")

        # 결과 포맷팅
        if isinstance(result, dict):
            result_str = str(result)
        else:
            result_str = str(result)

        return VoiceOrchestrationState(tool_results=f"\n[{selected_tool} 결과]\n{result_str}\n")

    except Exception as e:
        logger.error(f"Tool [{selected_tool}] 실행 실패: {e}", exc_info=True)
        return VoiceOrchestrationState(
            tool_results=f"\n[{selected_tool} 오류]\n{str(e)}\n",
            selected_tool=None,
        )
