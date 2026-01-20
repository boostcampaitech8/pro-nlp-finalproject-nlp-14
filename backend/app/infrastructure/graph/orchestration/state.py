import datetime
import operator
from typing import Annotated, Any, Dict, List, TypedDict

from langgraph.graph.message import add_messages


# State 정의
class GraphState(TypedDict):
    run_id: Annotated[str, "run_id"]
    executed_at: Annotated[datetime.datetime, "current_time"]

    # 주의: add_messages는 리스트 타입에 사용하는 것이 일반적입니다.
    query: Annotated[str, add_messages]
    user_id: Annotated[str, "user_id"]

    # Planning 관련
    plan: Annotated[str, add_messages]
    toolcalls: Annotated[str, "tool signal"]  # "TOOL_REQUIRED" or ""

    # Analysis 관련
    analysis: Annotated[str, add_messages]
    has_more_tasks: Annotated[bool, "has more tasks"]
    next_action: Annotated[str, add_messages]

    # Tool execution 관련
    tool_to_execute: Annotated[Dict[str, Any], "tool to execute"]
    executor_result: Annotated[str, operator.add]
    executed_tools: Annotated[List[Dict[str, Any]], operator.add]

    # Routing 관련
    next_node: Annotated[str, "next node to route"]

    # Response
    response: Annotated[str, operator.add]
