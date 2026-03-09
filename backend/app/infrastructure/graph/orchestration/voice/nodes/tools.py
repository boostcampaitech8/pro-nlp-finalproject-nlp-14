"""Voice 단순화된 Tool Execution Node - Query 도구만, HITL 없음"""

import json
import logging

from langchain_core.messages import ToolMessage

from app.infrastructure.graph.orchestration.shared.tools.registry import get_tool_by_name

from ..state import VoiceOrchestrationState

logger = logging.getLogger(__name__)


def _get_tool_call_id(state: VoiceOrchestrationState) -> str:
    """planner의 AIMessage에서 tool_call_id 추출."""
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return messages[-1].tool_calls[0]["id"]
    return "unknown"


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
    tool_call_id = _get_tool_call_id(state)

    if not selected_tool:
        logger.warning("No tool selected")
        content = "도구가 선택되지 않았습니다."
        return VoiceOrchestrationState(
            messages=[ToolMessage(content=content, tool_call_id=tool_call_id, name="unknown")],
            tool_results=content,
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    # Get the tool
    tool = get_tool_by_name(selected_tool)
    if not tool:
        logger.error(f"Tool not found: {selected_tool}")
        content = f"'{selected_tool}' 도구를 찾을 수 없습니다."
        return VoiceOrchestrationState(
            messages=[ToolMessage(content=content, tool_call_id=tool_call_id, name=selected_tool)],
            tool_results=content,
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    logger.info(f"Executing Query tool: {selected_tool}")

    try:
        # tool.coroutine 직접 호출 (_user_id는 InjectedToolArg로 스키마에 없어서 ainvoke로는 전달 불가)
        invoke_args = {"_user_id": user_id, **tool_args}
        result = await tool.coroutine(**invoke_args)
        logger.info(f"Tool [{selected_tool}] 실행 성공")
        logger.debug(f"Tool result: {str(result)[:200]}...")

        # 결과 포맷팅
        result_str = json.dumps(result, ensure_ascii=False, default=str) if isinstance(result, dict) else str(result)

        tool_results = f"\n[{selected_tool} 결과]\n{result_str}\n"
        return VoiceOrchestrationState(
            messages=[ToolMessage(content=tool_results, tool_call_id=tool_call_id, name=selected_tool)],
            tool_results=tool_results,
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    except Exception as e:
        logger.error(f"Tool [{selected_tool}] 실행 실패: {e}", exc_info=True)
        content = f"\n[{selected_tool} 오류]\n{str(e)}\n"
        return VoiceOrchestrationState(
            messages=[ToolMessage(content=content, tool_call_id=tool_call_id, name=selected_tool or "unknown")],
            tool_results=content,
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )
