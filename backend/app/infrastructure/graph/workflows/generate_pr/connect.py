"""generate_pr 그래프 노드 연결

노드와 엣지 구성
"""

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.generate_pr.nodes import (
    extract_chunked,
    extract_single,
    save_to_kg,
    route_by_token_count,
    validate_hard_gate,
)
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState


def build_generate_pr() -> StateGraph:
    """generate_pr 그래프 빌더 생성

    그래프 구조:
        START -> router -> [single_pass|chunked_pass] -> gate -> saver -> END
    """
    workflow = StateGraph(GeneratePrState)

    # 노드 등록 (역할 명사로 등록)
    workflow.add_node("router", route_by_token_count)
    workflow.add_node("single_pass", extract_single)
    workflow.add_node("chunked_pass", extract_chunked)
    workflow.add_node("gate", validate_hard_gate)
    workflow.add_node("saver", save_to_kg)

    # 엣지 연결
    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        lambda s: s.get("generate_pr_route", "short"),
        {
            "short": "single_pass",
            "long": "chunked_pass",
        },
    )
    workflow.add_edge("single_pass", "gate")
    workflow.add_edge("chunked_pass", "gate")
    workflow.add_edge("gate", "saver")
    workflow.add_edge("saver", END)

    return workflow
