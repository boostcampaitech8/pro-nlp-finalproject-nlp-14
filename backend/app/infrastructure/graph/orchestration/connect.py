"""Orchestration Workflow 구성 및 컴파일

워크플로우 빌더와 컴파일 함수를 분리하여 checkpointer 적용을 지원.

사용 예시:
    # checkpointer 포함 (멀티턴 지원)
    app = await get_compiled_app(with_checkpointer=True)
    config = {"configurable": {"thread_id": meeting_id}}
    result = await app.ainvoke(state, config)

    # checkpointer 없이 (단일 턴)
    app = await get_compiled_app(with_checkpointer=False)
    result = await app.ainvoke(state)
"""
import logging

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.checkpointer import get_checkpointer

from .nodes.answering import generate_answer
from .nodes.evaluation import evaluate_result
from .nodes.mit_tools_analyze import execute_mit_tools_analyze
from .nodes.mit_tools_search import execute_mit_tools_search
from .nodes.mit_tools import execute_mit_tools
from .nodes.planning import create_plan
from .nodes.simple_router import route_simple_query
from .nodes.tools import execute_tools
from .state import OrchestrationState

logger = logging.getLogger(__name__)

# Simple Router 후 라우팅: 간단한 쿼리면 generator로, 복잡하면 planner로
def route_after_simple_check(state: OrchestrationState) -> str:
    """간단한 쿼리 여부에 따라 라우팅"""
    if state.get("is_simple_query", False):
        return "generator"  # 간단한 쿼리면 직접 응답 생성
    return "planner"  # 복잡한 쿼리면 계획 수립


# Planning -> 도구 필요 여부에 따라 라우팅
def route_by_tool_need(state: OrchestrationState) -> str:
    """도구 필요 여부 및 HITL 상태에 따라 라우팅
    Returns:
        str: 다음 노드 이름
            - "tools": selected_tool이 있는 경우 (새 Tool 시스템)
            - "mit_tools": need_tools=True인 경우 (기존 MIT 검색 도구)
            - "generator": 그 외 경우 (직접 응답 생성)
    """
    # HITL 확인 대기 중이면 END (SSE로 클라이언트에 알림)
    if state.get("hitl_status") == "pending":
        return END

    # 새 Tool 시스템: selected_tool이 있으면 tools 노드로
    if state.get("selected_tool"): 
        return "tools"

    return "mit_tools_analyze" if state.get("need_tools", False) else "generator"

def route_after_tools(state: OrchestrationState) -> str:
    """Tool 실행 후 라우팅

    HITL pending 상태면 END로 가서 사용자 확인 대기,
    그 외에는 evaluator로 이동.
    """
    if state.get("hitl_status") == "pending":
        return END
    return "evaluator"



def route_by_evaluation(state: OrchestrationState) -> str:
    """평가 결과에 따라 라우팅: retry/replanning/success"""
    status = state.get("evaluation_status", "success")

    if status == "retry":
        return "mit_tools_analyze"
    elif status == "replanning":
        return "planner"
    return "generator"


def build_orchestration_workflow() -> StateGraph:
    """오케스트레이션 워크플로우 빌더 (checkpointer 없이)

    Returns:
        StateGraph: 컴파일 전 워크플로우 그래프

    Workflow:
        planner -> [tools | mit_tools | generator | END]
        tools -> [evaluator | END (HITL pending)]
        mit_tools -> evaluator
        evaluator -> [mit_tools | planner | generator]
        generator -> END
    """
    workflow = StateGraph(OrchestrationState)

    # 노드 등록
    workflow.add_node("simple_router", route_simple_query)  # 새로운 라우터 노드
    workflow.add_node("planner", create_plan)
    workflow.add_node("mit_tools_analyze", execute_mit_tools_analyze)
    workflow.add_node("mit_tools_search", execute_mit_tools_search)
    workflow.add_node("tools", execute_tools)  # 새 Tool 시스템 (HITL 지원)
    workflow.add_node("mit_tools", execute_mit_tools)  # 기존 MIT 검색 도구
    workflow.add_node("evaluator", evaluate_result)
    workflow.add_node("generator", generate_answer)

    # 엣지 연결
    workflow.set_entry_point("simple_router")  # Simple Router로 시작

    # Simple Router -> 조건부 라우팅
    workflow.add_conditional_edges(
        "simple_router",
        route_after_simple_check,
        {"generator": "generator", "planner": "planner"},
    )

    # Planning -> 도구 필요 여부 및 HITL 상태에 따라 라우팅
    workflow.add_conditional_edges(
        "planner",
        route_by_tool_need,
        {
            "tools": "tools",
            "mit_tools": "mit_tools",
            "mit_tools_analyze": "mit_tools_analyze",
            "generator": "generator",
            END: END,  # HITL pending 상태
        },
    )
    
    # Tools -> HITL 상태에 따라 라우팅
    workflow.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "evaluator": "evaluator",
            END: END,  # HITL pending 상태 (사용자 확인 대기)
        },

    )

    # MIT-Tools Analyze -> MIT-Tools Search (항상)
    workflow.add_edge("mit_tools_analyze", "mit_tools_search")

    # MIT-Tools Search -> Evaluator
    workflow.add_edge("mit_tools_search", "evaluator")

    # Evaluator -> 평가 결과에 따라 라우팅
    workflow.add_conditional_edges(
        "evaluator",
        route_by_evaluation,
        {"mit_tools_analyze": "mit_tools_analyze", "planner": "planner", "generator": "generator"},
    )

    # Generator -> END
    workflow.add_edge("generator", END)

    return workflow


async def get_compiled_app(*, with_checkpointer: bool = True) -> CompiledStateGraph:
    """컴파일된 그래프 반환 (checkpointer 선택적 적용)

    Args:
        with_checkpointer: True면 AsyncPostgresSaver 사용 (멀티턴 지원)

    Returns:
        CompiledStateGraph: 실행 가능한 컴파일된 그래프
    """
    workflow = build_orchestration_workflow()

    if with_checkpointer:
        checkpointer = await get_checkpointer()
        return workflow.compile(checkpointer=checkpointer)

    return workflow.compile()
