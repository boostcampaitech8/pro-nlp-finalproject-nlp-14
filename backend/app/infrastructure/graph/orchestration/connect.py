from langgraph.graph import END, StateGraph

from .nodes.answering import generate_answer
from .nodes.evaluation import evaluate_result
from .nodes.mit_tools import execute_mit_tools
from .nodes.planning import create_plan
from .state import OrchestrationState

# 워크플로우 생성
workflow = StateGraph(OrchestrationState)

# ===== 노드 등록 =====
workflow.add_node("planner", create_plan)
workflow.add_node("mit_tools", execute_mit_tools)
workflow.add_node("evaluator", evaluate_result)
workflow.add_node("generator", generate_answer)

# ===== 엣지 연결 =====

# 1. 시작점: Planning
workflow.set_entry_point("planner")

# 2. Planning -> Tool Call? 라우팅 (조건부 엣지)
#    - 도구 필요 -> mit_tools
#    - 도구 불필요 -> generator
def route_by_tool_need(state: OrchestrationState) -> str:
    """도구 호출 필요 여부를 판단하는 라우팅 함수
    
    Contract:
        reads: need_tools
        returns: 다음 노드명 (str)
    """
    need_tools = state.get('need_tools', False)
    return "mit_tools" if need_tools else "generator"

workflow.add_conditional_edges(
    "planner",
    route_by_tool_need,
    {
        "mit_tools": "mit_tools",
        "generator": "generator"
    }
)

# 3. MIT-Tools -> Evaluator
#    도구 실행 후 평가
workflow.add_edge("mit_tools", "evaluator")

# 4. Evaluator -> 평가 라우팅 (조건부 엣지)
#    - success: 최종 응답 생성
#    - retry: 같은 도구 재실행
#    - replanning: 계획 재수립
def route_by_evaluation(state: OrchestrationState) -> str:
    """평가 결과에 따라 다음 단계를 결정하는 라우팅 함수
    
    Contract:
        reads: evaluation_status
        returns: 다음 노드명 (str)
    """
    status = state.get('evaluation_status', 'success')

    if status == "retry":
        return "mit_tools"
    elif status == "replanning":
        return "planner"
    else:  # success
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

# 5. Generate Answer -> END
#    최종 응답 생성 후 종료
workflow.add_edge("generator", END)

# 워크플로우 컴파일
app = workflow.compile()

