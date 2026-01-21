import logging

from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


def executor(state: OrchestrationState):
    """실제 도구를 실행하는 노드"""
    logger.info("실행 단계 진입")

    tool_to_execute = state.get('tool_to_execute', {})
    tool_name = tool_to_execute.get('name', '')
    tool_params = tool_to_execute.get('params', {})

    logger.info(f"실행할 도구: {tool_name}")
    logger.info(f"파라미터: {tool_params}")

    # 실제 도구 실행 로직 (지금은 임시로 더미 데이터)
    # TODO: 실제 도구 호출 구현 필요
    result = f"[{tool_name}] 실행 결과: 임시 데이터"

    # 실행된 도구 기록
    executed_tools = state.get('executed_tools', [])
    executed_tools.append({
        'name': tool_name,
        'params': tool_params,
        'result': result
    })

    logger.info(f"실행 완료: {result}")

    return {
        "executor_result": result,
        "executed_tools": executed_tools
    }
