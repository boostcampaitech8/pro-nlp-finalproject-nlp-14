"""MIT Search 서브그래프의 연결 로직 및 워크플로우 빌더."""

import logging

from langgraph.graph import END, START, StateGraph

from .nodes.cypher_generation import cypher_generator_async
from .nodes.query_intent_analyzer import query_intent_analyzer_async
from .nodes.result_merger import result_merger_async
from .nodes.tool_retrieval import tool_executor_async
from .state import MitSearchState

logger = logging.getLogger(__name__)


def build_mit_search() -> StateGraph:
    """모든 노드와 엣지를 포함한 MIT Search 서브그래프 빌드.

            그래프 구조:
            START → query_intent_analyzer →
                    ↓
                cypher_generator → tool_executor → result_merger → END

    Returns:
        StateGraph (컴파일 전) - 컴파일은 graph.py에서 수행
    """
    logger.info("MIT Search 서브그래프 빌드 중")

    workflow = StateGraph(MitSearchState)

    # 노드 등록
    workflow.add_node("query_intent_analyzer", query_intent_analyzer_async)
    workflow.add_node("cypher_generator", cypher_generator_async)
    workflow.add_node("tool_executor", tool_executor_async)
    workflow.add_node("result_merger", result_merger_async)

    # 선형 부분: START → query_intent_analyzer
    workflow.add_edge(START, "query_intent_analyzer")

    # 의도 분석 후 Cypher 생성
    workflow.add_edge("query_intent_analyzer", "cypher_generator")

    # Cypher 파이프라인
    workflow.add_edge("cypher_generator", "tool_executor")

    # 결과 병합
    workflow.add_edge("tool_executor", "result_merger")

    # 병합 후 종료
    workflow.add_edge("result_merger", END)

    logger.info("MIT Search 서브그래프 빌드 완료")

    return workflow
