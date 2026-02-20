"""mit_mention 그래프 노드 연결

노드와 엣지 구성 (재시도 순환 포함)
"""

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.mit_mention.nodes import (
    execute_search,
    gather_context,
    generate_response,
    route_search_need,
    route_validation,
    validate_response,
)
from app.infrastructure.graph.workflows.mit_mention.state import MitMentionState


def route_after_search_check(state: MitMentionState) -> str:
    """검색 필요 여부에 따라 라우팅
    
    검색 필요: mit_search_tool 실행
    검색 불필요: context_gatherer로 직행
    """
    needs_search = state.get("mit_mention_needs_search", False)
    return "mit_search_tool" if needs_search else "context_gatherer"


def build_mit_mention() -> StateGraph:
    """mit_mention 그래프 빌더 생성

    그래프 구조:
        START -> search_router -> [검색 필요?]
                      ↓               ↓
                  (판단)        Yes: mit_search_tool
                               No: context_gatherer
                      ↓               ↓
              context_gatherer (검색 결과 + Meeting 컨텍스트)
                      ↓
              generator -> validator -> [route] -> END
                  ↑                        |
                  |________________________|
                      (재시도: generator)
    """
    workflow = StateGraph(MitMentionState)

    # 노드 등록 (역할 명사로 등록)
    workflow.add_node("search_router", route_search_need)
    workflow.add_node("mit_search_tool", execute_search)
    workflow.add_node("context_gatherer", gather_context)
    workflow.add_node("generator", generate_response)
    workflow.add_node("validator", validate_response)

    # 엣지 연결
    workflow.add_edge(START, "search_router")
    
    # search_router -> 조건부 라우팅
    workflow.add_conditional_edges(
        "search_router",
        route_after_search_check,
        {"mit_search_tool": "mit_search_tool", "context_gatherer": "context_gatherer"},
    )
    
    # mit_search_tool -> context_gatherer (검색 후 컨텍스트 수집)
    workflow.add_edge("mit_search_tool", "context_gatherer")
    
    workflow.add_edge("context_gatherer", "generator")
    workflow.add_edge("generator", "validator")

    # 조건부 엣지 (순환형 - 검증 실패 시 재생성)
    workflow.add_conditional_edges(
        "validator",
        route_validation,
        {"generator": "generator", "end": END},
    )

    return workflow
