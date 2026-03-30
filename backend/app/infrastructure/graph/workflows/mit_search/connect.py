"""MIT Search 서브그래프의 연결 로직 및 워크플로우 빌더."""

import logging

from langgraph.graph import END, START, StateGraph

from .nodes.cypher_generation import cypher_generator_async
from .nodes.query_intent_analyzer import query_intent_analyzer_async
from .nodes.tool_retrieval import tool_executor_async
from .state import MitSearchState

logger = logging.getLogger(__name__)


def build_mit_search() -> StateGraph:
    """모든 노드와 엣지를 포함한 MIT Search 서브그래프 빌드.

            그래프 구조:
            START → query_intent_analyzer → cypher_generator → tool_executor → END

    Returns:
        StateGraph (컴파일 전) - 컴파일은 graph.py에서 수행
    """
    logger.info("MIT Search 서브그래프 빌드 중")

    workflow = StateGraph(MitSearchState)

    # 노드 등록
    workflow.add_node("query_intent_analyzer", query_intent_analyzer_async)
    workflow.add_node("cypher_generator", cypher_generator_async)
    workflow.add_node("tool_executor", tool_executor_async)

    # 선형 파이프라인: START → query_intent_analyzer → cypher_generator → tool_executor → END
    workflow.add_edge(START, "query_intent_analyzer")
    workflow.add_edge("query_intent_analyzer", "cypher_generator")
    workflow.add_edge("cypher_generator", "tool_executor")
    workflow.add_edge("tool_executor", END)

    logger.info("MIT Search 서브그래프 빌드 완료")

    return workflow


def build_mit_search_from_cypher() -> StateGraph:
    """의도 분석 없이 Cypher 생성부터 시작하는 부분 MIT Search 서브그래프 빌드.

    오케스트레이션 그래프에서 mit_tools_analyze가 이미 query_intent를 생성했을 때 사용.

    그래프 구조:
        START → cypher_generator → tool_executor → END

    Returns:
        StateGraph (컴파일 전) - 컴파일은 graph.py에서 수행
    """
    logger.info("부분 MIT Search 서브그래프 빌드 중 (cypher부터 시작)")

    workflow = StateGraph(MitSearchState)

    # 노드 등록 (query_intent_analyzer 제외)
    workflow.add_node("cypher_generator", cypher_generator_async)
    workflow.add_node("tool_executor", tool_executor_async)

    # 선형 파이프라인: START → cypher_generator → tool_executor → END
    workflow.add_edge(START, "cypher_generator")
    workflow.add_edge("cypher_generator", "tool_executor")
    workflow.add_edge("tool_executor", END)

    logger.info("부분 MIT Search 서브그래프 빌드 완료")

    return workflow
