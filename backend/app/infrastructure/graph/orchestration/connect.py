from langgraph.graph import END, StateGraph

from .nodes.evaluator import evaluator
from .nodes.generate_response import generate_response
from .nodes.mit_tools import mit_tools
from .nodes.planner import planning
from .state import OrchestrationState

# 워크플로우 생성
workflow = StateGraph(OrchestrationState)

# ===== 노드 등록 =====
workflow.add_node("planning", planning)
workflow.add_node("mit_tools", mit_tools)
workflow.add_node("evaluator", evaluator)
workflow.add_node("generate_response", generate_response)

# ===== 엣지 연결 =====

# 1. 시작점: Planning
workflow.set_entry_point("planning")

# 2. Planning -> Tool Call? 라우팅 (조건부 엣지)
#    - 도구 필요 -> mit_tools
#    - 도구 불필요 -> generate_response
def tool_call_router(state: OrchestrationState) -> str:
    """도구 호출 필요 여부를 판단하는 라우터"""
    need_tools = state.get('need_tools', False)
    return "mit_tools" if need_tools else "generate_response"

workflow.add_conditional_edges(
    "planning",
    tool_call_router,
    {
        "mit_tools": "mit_tools",
        "generate_response": "generate_response"
    }
)

# 3. MIT-Tools -> Evaluator
#    도구 실행 후 평가
workflow.add_edge("mit_tools", "evaluator")

# 4. Evaluator -> 평가 라우팅 (조건부 엣지)
#    - success: 최종 응답 생성
#    - retry: 같은 도구 재실행
#    - replanning: 계획 재수립
def evaluation_router(state: OrchestrationState) -> str:
    """평가 결과에 따라 다음 단계를 결정하는 라우터"""
    status = state.get('evaluation_status', 'success')

    if status == "retry":
        return "mit_tools"
    elif status == "replanning":
        return "planning"
    else:  # success
        return "generate_response"

workflow.add_conditional_edges(
    "evaluator",
    evaluation_router,
    {
        "mit_tools": "mit_tools",
        "planning": "planning",
        "generate_response": "generate_response"
    }
)

# 5. Generate Response -> END
#    최종 응답 생성 후 종료
workflow.add_edge("generate_response", END)

# 워크플로우 컴파일
app = workflow.compile()

