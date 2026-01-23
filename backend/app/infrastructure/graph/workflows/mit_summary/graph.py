"""MIT Summary 그래프 (외부 API)"""

from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.workflows.mit_summary.connect import build_mit_summary


def get_mit_summary_graph(*, checkpointer=None) -> CompiledStateGraph:
    """MIT Summary 그래프 생성

    Args:
        checkpointer: 체크포인터 (서브그래프는 None 권장)

    Returns:
        컴파일된 MIT Summary 그래프
    """
    builder = build_mit_summary()
    return builder.compile(checkpointer=checkpointer)

