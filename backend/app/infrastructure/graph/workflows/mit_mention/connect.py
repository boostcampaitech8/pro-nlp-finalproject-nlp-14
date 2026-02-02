"""mit_mention 그래프 노드 연결

노드와 엣지 구성 (재시도 순환 포함)
"""

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.mit_mention.nodes import (
    gather_context,
    generate_response,
    route_validation,
    validate_response,
)
from app.infrastructure.graph.workflows.mit_mention.state import MitMentionState


def build_mit_mention() -> StateGraph:
    """mit_mention 그래프 빌더 생성

    그래프 구조:
        START -> context_gatherer -> generator -> validator -> [route] -> END
                                       ^                          |
                                       |__________________________|
                                            (재시도: generator)
    """
    workflow = StateGraph(MitMentionState)

    # 노드 등록 (역할 명사로 등록)
    workflow.add_node("context_gatherer", gather_context)
    workflow.add_node("generator", generate_response)
    workflow.add_node("validator", validate_response)

    # 엣지 연결
    workflow.add_edge(START, "context_gatherer")
    workflow.add_edge("context_gatherer", "generator")
    workflow.add_edge("generator", "validator")

    # 조건부 엣지 (순환형 - 검증 실패 시 재생성)
    workflow.add_conditional_edges(
        "validator",
        route_validation,
        {"generator": "generator", "end": END},
    )

    return workflow
