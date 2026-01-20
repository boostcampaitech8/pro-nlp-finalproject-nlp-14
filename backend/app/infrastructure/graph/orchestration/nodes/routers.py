import logging

from app.infrastructure.graph.orchestration.state import GraphState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


def should_use_tools(state: GraphState) -> GraphState:
    """도구 사용이 필요한지 판단하는 분기 노드 (Planning 이후)"""
    logger.info("도구 필요 여부 판단")

    tool_signal = state.get('toolcalls', "")

    if tool_signal:
        logger.info(">>> 결정: 도구 사용 필요 -> 분석 단계로")
        state["next_node"] = "analyzer"
    else:
        logger.info(">>> 결정: 도구 불필요 -> 응답 생성으로")
        state["next_node"] = "generate_response"
    
    return state


def check_more_tasks(state: GraphState) -> GraphState:
    """추가 작업이 있는지 판단하는 분기 노드 (Analyzer 이후)"""
    logger.info("추가 작업 필요 여부 판단")

    has_more = state.get('has_more_tasks', False)

    if has_more:
        logger.info(">>> 결정: 추가 작업 있음 -> 툴콜 생성으로")
        state["next_node"] = "toolcall_generator"
    else:
        logger.info(">>> 결정: 작업 완료 -> 응답 생성으로")
        state["next_node"] = "generate_response"
    
    return state
