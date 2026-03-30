"""mit_suggestion 그래프 노드 연결

노드와 엣지 구성 (컨텍스트 수집 → 생성)
"""

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.mit_suggestion.nodes import (
    gather_context,
    generate_new_decision,
)
from app.infrastructure.graph.workflows.mit_suggestion.state import MitSuggestionState


def build_mit_suggestion() -> StateGraph:
    """mit_suggestion 그래프 빌더 생성

    그래프 구조:
        START -> context_gatherer -> generator -> END

        컨텍스트 수집 후 생성:
        - context_gatherer: 회의 정보, 논의 이력, 관련 Decision 수집
        - generator: 수집된 컨텍스트를 바탕으로 새 Decision 생성
    """
    workflow = StateGraph(MitSuggestionState)

    # 노드 등록
    workflow.add_node("context_gatherer", gather_context)
    workflow.add_node("generator", generate_new_decision)

    # 엣지 연결 (선형: 컨텍스트 수집 → 생성)
    workflow.add_edge(START, "context_gatherer")
    workflow.add_edge("context_gatherer", "generator")
    workflow.add_edge("generator", END)

    return workflow
