"""MIT Search 서브그래프: 컴파일된 그래프 인스턴스."""

from .connect import build_mit_search


def get_graph(*, checkpointer=None):
    """선택적 checkpointer를 포함한 MIT Search 서브그래프 반환.
    Args:
        checkpointer: 영속성을 위한 선택적 checkpointer (내부 사용 전용)
    Returns:
        오케스트레이션 통합 준비가 완료된 컴파일된 StateGraph
    """
    builder = build_mit_search()
    return builder.compile(checkpointer=checkpointer)


# 컴파일된 그래프 인스턴스 export (기본값, checkpointer 없음)
mit_search_graph = get_graph()
