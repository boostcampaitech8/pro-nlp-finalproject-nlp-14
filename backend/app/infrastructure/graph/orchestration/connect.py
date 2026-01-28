from langgraph.graph import END, StateGraph

from .nodes.answering import generate_answer
from .nodes.evaluation import evaluate_result
from .nodes.mit_tools import execute_mit_tools
from .nodes.planning import create_plan
from .state import OrchestrationState

# 워크플로우 생성
workflow = StateGraph(OrchestrationState)

# 노드 등록
workflow.add_node("planner", create_plan)
workflow.add_node("mit_tools", execute_mit_tools)
workflow.add_node("evaluator", evaluate_result)
workflow.add_node("generator", generate_answer)

# 엣지 연결
workflow.set_entry_point("planner")

# Planning -> 도구 필요 여부에 따라 라우팅
def route_by_tool_need(state: OrchestrationState) -> str:
    """도구 필요 여부에 따라 라우팅"""
    return "mit_tools" if state.get('need_tools', False) else "generator"

workflow.add_conditional_edges(
    "planner",
    route_by_tool_need,
    {
        "mit_tools": "mit_tools",
        "generator": "generator"
    }
)

# MIT-Tools -> Evaluator
workflow.add_edge("mit_tools", "evaluator")

# Evaluator -> 평가 결과에 따라 라우팅
def route_by_evaluation(state: OrchestrationState) -> str:
    """평가 결과에 따라 라우팅: retry/replanning/success"""
    status = state.get('evaluation_status', 'success')
    
    if status == "retry":
        return "mit_tools"
    elif status == "replanning":
        return "planner"
    return "generator"

workflow.add_conditional_edges(
    "evaluator",
    route_by_evaluation,
    {
        "mit_tools": "mit_tools",
        "planner": "planner",
        "generator": "generator"
    }
)

# Generator -> END
workflow.add_edge("generator", END)

# 워크플로우 컴파일
app = workflow.compile()

