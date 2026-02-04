import datetime
import operator
from typing import Annotated, List, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


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
    tool_results: Annotated[str, operator.add]  # mit-Tools 실행 결과 (누적) - mit_search 결과 포함
    retry_count: Annotated[int, "retry count"]  # 재시도 횟수

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
    skip_planning: NotRequired[bool]

    # Channel (voice or text)
    channel: NotRequired[str]  # "voice" or "text", default: "voice"
