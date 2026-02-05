import datetime
import operator
from typing import Annotated, List, Literal, NotRequired, TypedDict

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
    skip_planning: NotRequired[bool]

    # Channel (voice or text)
    channel: NotRequired[str]  # "voice" or "text", default: "voice"
    # === NEW: Interaction Mode & Tool Selection ===
    interaction_mode: NotRequired[Literal["voice", "spotlight"]]  # 상호작용 모드

    # Tool selection (Planning에서 설정)
    selected_tool: NotRequired[str]  # 선택된 도구 이름
    tool_args: NotRequired[dict]  # 도구 인자 (LLM이 추출)
    tool_category: NotRequired[Literal["query", "mutation"]]  # 도구 카테고리

    # === NEW: HITL (Human-in-the-Loop) Fields ===
    hitl_status: NotRequired[Literal["none", "pending", "confirmed", "cancelled", "executed"]]
    hitl_tool_name: NotRequired[str]  # HITL 대기 중인 도구 이름
    hitl_extracted_params: NotRequired[dict]  # LLM이 추출한 파라미터
    hitl_params_display: NotRequired[dict]  # UUID → 이름 변환된 표시용 값
    hitl_missing_params: NotRequired[list[str]]  # 누락된 필수 파라미터
    hitl_confirmation_message: NotRequired[str]  # 사용자에게 보여줄 확인 메시지
    hitl_required_fields: NotRequired[list[dict]]  # 필수 입력 필드 스키마
    hitl_display_template: NotRequired[str]  # 자연어 템플릿 ({{param}}이 input으로 대체됨)

    # 사용자 컨텍스트 (SPOTLIGHT 세션 시작 시 주입)
    user_context: NotRequired[dict]
    # {
    #   "user_id": "...",
    #   "teams": [{"id": "...", "name": "..."}],
    #   "current_time": "2025-01-15T14:30:00+09:00"  # ISO 형식
    # }
