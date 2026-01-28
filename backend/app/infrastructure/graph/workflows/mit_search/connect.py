"""MIT Search 서브그래프의 연결 로직 및 워크플로우 빌더."""

import logging
from langgraph.graph import StateGraph, START, END
from .state import MitSearchState
from .nodes.query_rewriting import query_rewriter_async
from .nodes.filter_extraction import filter_extractor_async
from .nodes.cypher_generation import cypher_generator_async
from .nodes.tool_retrieval import tool_executor_async
from .nodes.reranking import reranker_async
from .nodes.selection import selector_async

logger = logging.getLogger(__name__)


def build_mit_search() -> StateGraph:
    """모든 노드와 엣지를 포함한 MIT Search 서브그래프 빌드.

    그래프 구조 (선형 파이프라인):
        START → query_rewriter → filter_extractor → cypher_generator →
        tool_executor → reranker → selector → END

    Returns:
        StateGraph (컴파일 전) - 컴파일은 graph.py에서 수행
    """
    logger.info("MIT Search 서브그래프 빌드 중")

    # MitSearchState로 그래프 초기화
    workflow = StateGraph(MitSearchState)

    # 노드 추가 (오케스트레이션 호환을 위해 async 구현 사용)
    workflow.add_node("query_rewriter", query_rewriter_async)
    workflow.add_node("filter_extractor", filter_extractor_async)
    workflow.add_node("cypher_generator", cypher_generator_async)
    workflow.add_node("tool_executor", tool_executor_async)
    workflow.add_node("reranker", reranker_async)
    workflow.add_node("selector", selector_async)

    # 엣지 정의 (선형 흐름 - 조건부 라우팅 없음)
    workflow.add_edge(START, "query_rewriter")
    workflow.add_edge("query_rewriter", "filter_extractor")
    workflow.add_edge("filter_extractor", "cypher_generator")
    workflow.add_edge("cypher_generator", "tool_executor")
    workflow.add_edge("tool_executor", "reranker")
    workflow.add_edge("reranker", "selector")
    workflow.add_edge("selector", END)

    logger.info("MIT Search 서브그래프 빌드 완료")

    return workflow
