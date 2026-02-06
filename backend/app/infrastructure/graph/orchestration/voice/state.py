"""Voice Orchestration State - 회의 중 실시간 질의응답 전용 상태"""

from datetime import datetime
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


RESET_TOOL_RESULTS = "__CLEAR_TOOL_RESULTS__"


def tool_results_reducer(current: str | None, new: str | None) -> str:
    """tool_results 누적/리셋을 위한 reducer."""
    if new == RESET_TOOL_RESULTS:
        return ""
    if current is None:
        current = ""
    if new is None:
        return current
    return current + new


class VoiceOrchestrationState(TypedDict):
    """Voice 모드 전용 상태 스키마

    Voice 모드는 회의 중 실시간 질의응답에 특화되어 있으며:
    - meeting_id를 통해 회의 컨텍스트 유지
    - Query 도구만 사용 (MIT Search, 회의/팀 조회)
    - HITL(Human-in-the-Loop)는 지원하지 않음
    - user_context는 사용하지 않음 (meeting_id로 컨텍스트 파악)
    """

    # 실행 메타데이터
    run_id: Annotated[str, "run_id"]
    executed_at: Annotated[datetime, "current_time"]

    # 사용자 및 회의 식별
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: Annotated[str, "user_id"]
    meeting_id: Annotated[str, "meeting_id"]  # Voice 전용: 현재 진행 중인 회의 ID
    
    # Simple Query Routing
    is_simple_query: NotRequired[bool]
    simple_router_output: NotRequired[dict]
    
    # Planning
    plan: Annotated[str, "current plan"]
    need_tools: Annotated[bool, "tools needed"]
    can_answer: NotRequired[bool]
    missing_requirements: NotRequired[list[str]]
    
    # Tool execution (Query tools only)
    selected_tool: NotRequired[str]
    tool_args: NotRequired[dict]
    tool_category: NotRequired[Literal["query"]]  # Voice는 query만 허용
    tool_results: Annotated[str, tool_results_reducer]
    retry_count: Annotated[int, "retry count"]
    
    # MIT Search 관련
    mit_search_primary_entity: NotRequired[str]
    mit_search_query_intent: NotRequired[dict]
    
    # Evaluation
    evaluation: Annotated[str, "evaluation result"]
    evaluation_status: Annotated[str, "evaluation status"]
    evaluation_reason: Annotated[str, "evaluation reason"]
    next_subquery: NotRequired[str]
    
    # Response
    response: Annotated[str, "final response"]
    
    # Context Engineering
    planning_context: NotRequired[str]
    additional_context: NotRequired[str]
    skip_planning: NotRequired[bool]
