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
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.checkpointer import get_checkpointer

from .nodes.answering import generate_answer
from .nodes.evaluation import evaluate_result
from .nodes.mit_tools import execute_mit_tools
from .nodes.planning import create_plan
from .state import OrchestrationState


def route_by_tool_need(state: OrchestrationState) -> str:
    """도구 필요 여부에 따라 라우팅"""
    return "mit_tools" if state.get("need_tools", False) else "generator"


def route_by_evaluation(state: OrchestrationState) -> str:
    """평가 결과에 따라 라우팅: retry/replanning/success"""
    status = state.get("evaluation_status", "success")

    if status == "retry":
        return "mit_tools"
    elif status == "replanning":
        return "planner"
    return "generator"


def build_orchestration_workflow() -> StateGraph:
    """오케스트레이션 워크플로우 빌더 (checkpointer 없이)

    Returns:
        StateGraph: 컴파일 전 워크플로우 그래프
    """
    workflow = StateGraph(OrchestrationState)

    # 노드 등록
    workflow.add_node("planner", create_plan)
    workflow.add_node("mit_tools", execute_mit_tools)
    workflow.add_node("evaluator", evaluate_result)
    workflow.add_node("generator", generate_answer)

    # 엣지 연결
    workflow.set_entry_point("planner")

    # Planning -> 도구 필요 여부에 따라 라우팅
    workflow.add_conditional_edges(
        "planner",
        route_by_tool_need,
        {"mit_tools": "mit_tools", "generator": "generator"},
    )

    # MIT-Tools -> Evaluator
    workflow.add_edge("mit_tools", "evaluator")

    # Evaluator -> 평가 결과에 따라 라우팅
    workflow.add_conditional_edges(
        "evaluator",
        route_by_evaluation,
        {"mit_tools": "mit_tools", "planner": "planner", "generator": "generator"},
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
