"""Spotlight Orchestration State - 독립적인 회의 관리 및 조회 전용 상태"""

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


class SpotlightOrchestrationState(TypedDict):
    """Spotlight 모드 전용 상태 스키마

    Spotlight 모드는 독립적인 회의 관리 및 조회에 특화되어 있으며:
    - user_context를 통해 사용자 및 팀 정보 제공
    - Query + Mutation 도구 모두 사용 (회의 생성/수정 포함)
    - HITL(Human-in-the-Loop) 지원 (Mutation 도구 실행 전 사용자 확인)
    - meeting_id는 사용하지 않음 (회의 컨텍스트 무관)
    """

    # 실행 메타데이터
    run_id: Annotated[str, "run_id"]
    executed_at: Annotated[datetime, "current_time"]

    # 사용자 식별 및 컨텍스트
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: Annotated[str, "user_id"]
    user_context: NotRequired[dict]  # Spotlight 전용: {"teams": [...], "current_time": "..."}

    # Simple Query Routing
    is_simple_query: NotRequired[bool]
    simple_router_output: NotRequired[dict]

    # Planning
    plan: Annotated[str, "current plan"]
    need_tools: Annotated[bool, "tools needed"]
    can_answer: NotRequired[bool]
    missing_requirements: NotRequired[list[str]]

    # Tool execution (Query + Mutation tools)
    selected_tool: NotRequired[str]
    tool_args: NotRequired[dict]
    tool_category: NotRequired[Literal["query", "mutation"]]  # Spotlight는 둘 다 허용
    tool_results: Annotated[str, tool_results_reducer]
    retry_count: Annotated[int, "retry count"]

    # MIT Search 관련
    mit_search_primary_entity: NotRequired[str]
    mit_search_query_intent: NotRequired[dict]

    # Replanning
    next_subquery: NotRequired[str]

    # Response
    response: Annotated[str, "final response"]

    # Context Engineering
    planning_context: NotRequired[str]
    additional_context: NotRequired[str]
    skip_planning: NotRequired[bool]

    # HITL (Human-in-the-Loop) - Spotlight 전용
    hitl_status: NotRequired[Literal["none", "pending", "confirmed", "cancelled", "executed"]]
    hitl_tool_name: NotRequired[str]
    hitl_extracted_params: NotRequired[dict]
    hitl_params_display: NotRequired[dict]
    hitl_missing_params: NotRequired[list[str]]
    hitl_confirmation_message: NotRequired[str]
    hitl_required_fields: NotRequired[list[dict]]
    hitl_display_template: NotRequired[str]
    hitl_request_id: NotRequired[str]
