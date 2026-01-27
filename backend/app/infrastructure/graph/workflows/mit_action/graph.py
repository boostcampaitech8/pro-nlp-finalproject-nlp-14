"""mit_action 컴파일된 그래프"""

from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.workflows.mit_action.connect import build_mit_action


def get_graph(*, checkpointer=None) -> CompiledStateGraph:
    """mit_action 그래프 반환

    서브그래프이므로 checkpointer 없이 컴파일 (부모와 공유)
    """
    workflow = build_mit_action()
    return workflow.compile(checkpointer=checkpointer)


# 서브그래프 인스턴스 (orchestration에서 import 시 사용)
mit_action_graph = get_graph()
