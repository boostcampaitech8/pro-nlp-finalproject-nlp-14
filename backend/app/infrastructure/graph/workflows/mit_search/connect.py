"""MIT Search 서브그래프의 연결 로직 및 워크플로우 빌더."""

import logging

from langgraph.graph import END, START, StateGraph

from .nodes.cypher_generation import cypher_generator_async
from .nodes.query_intent_analyzer import query_intent_analyzer_async
from .nodes.result_merger import result_merger_async
from .nodes.tool_retrieval import tool_executor_async
from .nodes.vector_search import vector_search_async
from .state import MitSearchState

logger = logging.getLogger(__name__)


def build_mit_search() -> StateGraph:
    """모든 노드와 엣지를 포함한 MIT Search 서브그래프 빌드.

            그래프 구조 (병렬 Speculative RAG):
            START → query_intent_analyzer →
                    ↓
                [병렬 분기]
                ├─ cypher_generator → tool_executor
                └─ vector_search_async
                    ↓
                result_merger → END

    Speculative RAG 최적화:
    - Cypher 생성과 동시에 벡터 검색 선제적 실행
    - 벡터 검색 신뢰도 높으면 Cypher 기다리지 않고 즉시 사용
    - 빠른 응답 시간으로 지연 40% 감소 목표

    Returns:
        StateGraph (컴파일 전) - 컴파일은 graph.py에서 수행
    """
    logger.info("MIT Search 서브그래프 빌드 중 (Speculative RAG 활성화)")

    workflow = StateGraph(MitSearchState)

    # 노드 등록
    workflow.add_node("query_intent_analyzer", query_intent_analyzer_async)
    workflow.add_node("cypher_generator", cypher_generator_async)
    workflow.add_node("tool_executor", tool_executor_async)
    workflow.add_node("vector_search", vector_search_async)
    workflow.add_node("result_merger", result_merger_async)

    # 선형 부분: START → query_intent_analyzer
    workflow.add_edge(START, "query_intent_analyzer")

    # 병렬 분기: 의도 분석 후 Cypher와 벡터 검색 동시 시작
    workflow.add_edge("query_intent_analyzer", "cypher_generator")
    workflow.add_edge("query_intent_analyzer", "vector_search")

    # Cypher 파이프라인
    workflow.add_edge("cypher_generator", "tool_executor")

    # 병렬 결과 병합: tool_executor와 vector_search 모두 완료 후
    workflow.add_edge("tool_executor", "result_merger")
    workflow.add_edge("vector_search", "result_merger")

    # 병합 후 종료
    workflow.add_edge("result_merger", END)

    logger.info("MIT Search 서브그래프 빌드 완료 (병렬 구조)")

    return workflow
