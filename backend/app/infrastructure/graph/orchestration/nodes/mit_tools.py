import logging

from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


def mit_tools(state: OrchestrationState):
    """
    MIT-Tools 노드
    나중에 summary, search 등 다양한 서브그래프로 구성될 예정
    현재는 pass로 구현하여 아무것도 반환하지 않음
    """
    logger.info("MIT-Tools 단계 진입")

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    plan = state.get('plan', '')
    retry_count = state.get('retry_count', 0)

    logger.info(f"사용자 쿼리: {query}")
    logger.info(f"계획: {plan}")
    logger.info(f"재시도 횟수: {retry_count}")

    # TODO: 나중에 실제 도구 실행 로직 구현
    # - search: 웹 검색
    # - summary: 문서 요약
    # - 기타 서브그래프들

    # 현재는 임시 구현
    logger.info("MIT-Tools: 현재 구현 안됨 (pass)")

    # 나중을 위한 구조:
    # tool_result = execute_subgraph(plan, query)
    # return {"tool_results": tool_result}

    # 임시로 빈 결과 반환
    return {
        "tool_results": ""
    }
