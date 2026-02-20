"""mit_mention 컴파일된 그래프"""

from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.workflows.mit_mention.connect import build_mit_mention


def get_graph(*, checkpointer=None) -> CompiledStateGraph:
    """mit_mention 그래프 반환

    독립 그래프 - ARQ worker에서 직접 호출
    """
    workflow = build_mit_mention()
    return workflow.compile(checkpointer=checkpointer)


# 그래프 인스턴스 (ARQ worker에서 import 시 사용)
mit_mention_graph = get_graph()
