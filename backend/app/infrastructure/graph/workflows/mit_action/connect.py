"""mit_action 그래프 노드 연결

노드와 엣지 구성 (순환형 구조 포함)
"""

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.mit_action.nodes import (
    evaluate_actions,
    extract_actions,
    route_eval,
    save_actions,
)
from app.infrastructure.graph.workflows.mit_action.state import MitActionState


def build_mit_action() -> StateGraph:
    """mit_action 그래프 빌더 생성

    그래프 구조:
        START -> extractor -> evaluator -> [route_eval] -> saver -> END
                    ^                           |
                    |___________________________|
                           (재시도: extractor)
    """
    workflow = StateGraph(MitActionState)

    # 노드 등록 (역할 명사로 등록)
    workflow.add_node("extractor", extract_actions)
    workflow.add_node("evaluator", evaluate_actions)
    workflow.add_node("saver", save_actions)

    # 엣지 연결
    workflow.add_edge(START, "extractor")
    workflow.add_edge("extractor", "evaluator")

    # 조건부 엣지 (순환형 - 평가 실패 시 재시도)
    workflow.add_conditional_edges(
        "evaluator",
        route_eval,
        {"extractor": "extractor", "saver": "saver"},
    )

    workflow.add_edge("saver", END)

    return workflow
