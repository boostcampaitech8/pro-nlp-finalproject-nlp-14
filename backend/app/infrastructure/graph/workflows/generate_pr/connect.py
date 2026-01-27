"""generate_pr 그래프 노드 연결

노드와 엣지 구성
"""

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.generate_pr.nodes import (
    extract_agendas,
    save_to_kg,
)
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState


def build_generate_pr() -> StateGraph:
    """generate_pr 그래프 빌더 생성

    그래프 구조:
        START -> extractor -> saver -> END
    """
    workflow = StateGraph(GeneratePrState)

    # 노드 등록 (역할 명사로 등록)
    workflow.add_node("extractor", extract_agendas)
    workflow.add_node("saver", save_to_kg)

    # 엣지 연결
    workflow.add_edge(START, "extractor")
    workflow.add_edge("extractor", "saver")
    workflow.add_edge("saver", END)

    return workflow
