from langgraph.graph import END, StateGraph

from .nodes.generate_response import generate_response
from .nodes.mit_tools_response import mit_tools_response
from .nodes.planning import planning
from .nodes.tool_call import tool_call
from .state import GraphState

workflow = StateGraph(GraphState)

# 노드 등록
workflow.add_node("planning", planning)
workflow.add_node("mit_tools_response", mit_tools_response)
workflow.add_node("generate_response", generate_response)

# 엣지 연결
# 1. start -> planning
workflow.set_entry_point("planning")

# 2. Planning -> 분기 -> Tools or Response
workflow.add_conditional_edges(
    "planning",
    tool_call,
    {
        "mit_tools":"mit_tools_response",
        "generate_response":"generate_response"
    }
)

# 3. Mit-Tools -> Response
workflow.add_edge("mit_tools_response", "generate_response")

# 4. Response -> 종료
workflow.add_edge("generate_response", END)

app = workflow.compile()
