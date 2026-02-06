import datetime
from typing import Annotated, List, Literal, NotRequired, TypedDict

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


# State 정의
class OrchestrationState(TypedDict):
    run_id: Annotated[str, "run_id"]
    executed_at: Annotated[datetime.datetime, "current_time"]

    # 채팅 메시지
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: Annotated[str, "user_id"]

    # Simple Query Routing 관련
    is_simple_query: NotRequired[bool]  # 간단한 쿼리 여부
    simple_router_output: NotRequired[dict]  # 라우터 분석 결과 (category, confidence, reasoning)

    # Planning 관련
    plan: Annotated[str, "current plan"]  # 현재 계획
    need_tools: Annotated[bool, "tools needed"]  # 도구 필요 여부
    can_answer: NotRequired[bool]  # 현재 도구/로직으로 답변 가능 여부
    missing_requirements: NotRequired[list[str]]  # 부족한 도구/정보 목록

    # Tool execution 관련
    tool_results: Annotated[str, tool_results_reducer]  # mit-Tools 실행 결과 (누적) - mit_search 결과 포함
    retry_count: Annotated[int, "retry count"]  # 재시도 횟수

    # MIT Search 의도 분석 결과 (event streaming용)
    mit_search_primary_entity: NotRequired[str]  # 검색 대상 엔티티
    mit_search_query_intent: NotRequired[dict]  # 전체 의도 분석 결과

    # Evaluation 관련
    evaluation: Annotated[str, "evaluation result"]  # 평가 내용
    evaluation_status: Annotated[str, "evaluation status"]  # "retry", "success", "replanning"
    evaluation_reason: Annotated[str, "evaluation reason"]  # 평가 이유
    next_subquery: NotRequired[str]  # replanning 시 다음 검색 쿼리 (서브-쿼리)

    # Response
    response: Annotated[str, "final response"]  # 최종 응답 (덮어쓰기)

    # Context Engineering (optional)
    planning_context: NotRequired[str]
    additional_context: NotRequired[str]

    # Tool selection (Planning에서 설정)
    selected_tool: NotRequired[str]  # 선택된 도구 이름
    tool_args: NotRequired[dict]  # 도구 인자 (LLM이 추출)
    tool_category: NotRequired[Literal["query", "mutation"]]  # 도구 카테고리
    auto_cancelled: NotRequired[bool]  # HITL 자동 취소 여부 (silent cancel)

    # 사용자 컨텍스트 (SPOTLIGHT 세션 시작 시 주입)
    user_context: NotRequired[dict]
    # {
    #   "user_id": "...",
    #   "teams": [{"id": "...", "name": "..."}],
    #   "current_time": "2025-01-15T14:30:00+09:00"  # ISO 형식
    # }
