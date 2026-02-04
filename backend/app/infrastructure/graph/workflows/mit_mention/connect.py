"""mit_mention 그래프 노드 연결

노드와 엣지 구성 (재시도 순환 + KG 검색 포함)
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.mit_mention.nodes import (
    gather_context,
    generate_response,
    route_validation,
    validate_response,
)
from app.infrastructure.graph.workflows.mit_mention.nodes.knowledge_search import (
    search_knowledge_graph,
)
from app.infrastructure.graph.workflows.mit_mention.nodes.search_router import (
    route_search_need,
)
from app.infrastructure.graph.workflows.mit_mention.state import MitMentionState


def conditional_search_routing(
    state: MitMentionState,
) -> Literal["knowledge_searcher", "generator"]:
    """검색 필요 여부에 따라 라우팅

    Returns:
        "knowledge_searcher" if search needed, else "generator"
    """
    needs_search = state.get("mit_mention_needs_search", False)
    return "knowledge_searcher" if needs_search else "generator"


def build_mit_mention() -> StateGraph:
    """mit_mention 그래프 빌더 생성

    그래프 구조:
        START -> context_gatherer -> search_router -> [conditional] -> knowledge_searcher (if needed)
                                                                     -> generator
        knowledge_searcher -> generator -> validator -> [route] -> END
                                            ^                       |
                                            |_______________________|
                                                (재시도: generator)
    """
    workflow = StateGraph(MitMentionState)

    # 노드 등록 (역할 명사로 등록)
    workflow.add_node("context_gatherer", gather_context)
    workflow.add_node("search_router", route_search_need)
    workflow.add_node("knowledge_searcher", search_knowledge_graph)
    workflow.add_node("generator", generate_response)
    workflow.add_node("validator", validate_response)

    # 엣지 연결
    workflow.add_edge(START, "context_gatherer")
    workflow.add_edge("context_gatherer", "search_router")

    # 조건부 엣지: 검색 필요 여부에 따라 분기
    workflow.add_conditional_edges(
        "search_router",
        conditional_search_routing,
        {
            "knowledge_searcher": "knowledge_searcher",
            "generator": "generator",
        },
    )

    workflow.add_edge("knowledge_searcher", "generator")
    workflow.add_edge("generator", "validator")

    # 조건부 엣지 (순환형 - 검증 실패 시 재생성)
    workflow.add_conditional_edges(
        "validator",
        route_validation,
        {"generator": "generator", "end": END},
    )

    return workflow
