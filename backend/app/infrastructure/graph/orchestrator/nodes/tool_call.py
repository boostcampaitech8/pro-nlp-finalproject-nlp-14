import logging
from typing import Literal

from app.infrastructure.graph.orchestrator.state import GraphState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)

# tool_call (conditional node)
def tool_call(state: GraphState) -> Literal["mit_tools", "generate_response"]:
    '''
    tool call 사용하는지 안하는지 분기 노드
    '''
    logger.info("Tool_call 단계 진입")

    # Planning 노드에서 True였으면 "TOOL_REQUIRED" 문자열이 들어있고, 아니면 빈 문자열임
    tool_signal = state.get('toolcalls', "")

    if tool_signal:  # 문자열이 있으면(True)
        logger.info(">>> 결정: Tool Call 사용")
        return "mit_tools"
    else:            # 문자열이 비어있으면(False)
        logger.info(">>> 결정: Tool Call 미사용")
        return "generate_response"
