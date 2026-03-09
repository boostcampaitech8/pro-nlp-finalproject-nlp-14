"""generate_pr 컴파일된 그래프"""

from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.workflows.generate_pr.connect import build_generate_pr


def get_graph(*, checkpointer=None) -> CompiledStateGraph:
    """generate_pr 그래프 반환

    서브그래프이므로 checkpointer 없이 컴파일 (부모와 공유)
    """
    workflow = build_generate_pr()
    return workflow.compile(checkpointer=checkpointer)


# 그래프 인스턴스 (import 시 사용)
generate_pr_graph = get_graph()
