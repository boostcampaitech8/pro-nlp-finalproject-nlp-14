import logging

from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


async def execute_mit_tools(state: OrchestrationState) -> OrchestrationState:
    """MIT-Tools 실행 노드

    Contract:
        reads: messages, retry_count
        writes: tool_results
        side-effects: 서브그래프 실행 (search, summary 등)
        failures: TOOL_EXECUTION_FAILED -> 빈 결과 반환

    Note: summary, search 등 다양한 서브그래프로 구성될 예정
    """
    logger.info("MIT-Tools 단계 진입")

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    retry_count = state.get('retry_count', 0)

    logger.info(f"쿼리: {query[:50]}..., 재시도: {retry_count}")

    # TODO: 실제 도구 실행 로직 구현
    # tool_result = await execute_subgraph(plan, query)

    return OrchestrationState(tool_results="")
