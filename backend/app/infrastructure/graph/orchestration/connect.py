from langgraph.graph import END, StateGraph

from .nodes.analyzer import analyzer
from .nodes.executor import executor
from .nodes.generate_response import generate_response
from .nodes.planner import planning
from .nodes.routers import check_more_tasks, should_use_tools
from .nodes.toolcall_generator import toolcall_generator
from .state import GraphState

# 워크플로우 생성
workflow = StateGraph(GraphState)

# ===== 노드 등록 =====
workflow.add_node("planning", planning)
workflow.add_node("tool_router", should_use_tools)
workflow.add_node("analyzer", analyzer)
workflow.add_node("task_router", check_more_tasks)
workflow.add_node("toolcall_generator", toolcall_generator)
workflow.add_node("executor", executor)
workflow.add_node("generate_response", generate_response)

# ===== 엣지 연결 =====

# 1. 시작점: Planning
workflow.set_entry_point("planning")

# 2. Planning -> Tool Router
workflow.add_edge("planning", "tool_router")

# 3. Tool Router -> 도구 필요? 분기
#    - 도구 필요 YES -> Analyzer
#    - 도구 필요 NO -> Generate Response
workflow.add_conditional_edges(
    "tool_router",
    lambda s: s["next_node"],
    {
        "analyzer": "analyzer",
        "generate_response": "generate_response"
    }
)

# 4. Analyzer -> Task Router
workflow.add_edge("analyzer", "task_router")

# 5. Task Router -> 다음 작업 가능? 분기
#    - 추가 작업 있음 -> Toolcall Generator
#    - 추가 작업 없음 -> Generate Response (최종 응답)
workflow.add_conditional_edges(
    "task_router",
    lambda s: s["next_node"],
    {
        "toolcall_generator": "toolcall_generator",
        "generate_response": "generate_response"
    }
)

# 6. Toolcall Generator -> Executor
#    파라미터 적절 생성 후 실행
workflow.add_edge("toolcall_generator", "executor")

# 7. Executor -> Analyzer
#    실행 후 다시 분석으로 돌아가 추가 작업 확인
workflow.add_edge("executor", "analyzer")

# 8. Generate Response -> END
#    최종 응답 생성 후 종료
workflow.add_edge("generate_response", END)

# 워크플로우 컴파일
app = workflow.compile()
