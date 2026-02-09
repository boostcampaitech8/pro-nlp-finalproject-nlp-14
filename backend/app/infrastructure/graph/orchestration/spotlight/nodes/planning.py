import logging

from langchain_core.messages import AIMessage

# 공유 도구 레지스트리에서 모든 도구 가져오기 (Query + Mutation)
import app.infrastructure.graph.orchestration.shared.tools  # noqa: F401
from app.infrastructure.graph.integration.llm import get_planner_llm
from app.infrastructure.graph.orchestration.shared.message_utils import (
    build_planner_chat_messages,
    extract_last_human_query,
)
from app.infrastructure.graph.orchestration.shared.planning_utils import (
    MUTATION_SUCCESS_MARKERS,
    PLANNING_MAX_RETRY,
    detect_composite_query,
    extract_next_step_query,
    is_subquery,
)
from app.infrastructure.graph.orchestration.shared.tools.registry import (
    get_all_tools,
    get_tool_category,
)
from app.prompt.v1.orchestration.planning import TOOL_UNAVAILABLE_MESSAGES  # noqa: F401
from app.prompt.v1.orchestration.spotlight.planning import build_spotlight_system_prompt

from ..state import SpotlightOrchestrationState

logger = logging.getLogger(__name__)


async def create_plan(state: SpotlightOrchestrationState) -> SpotlightOrchestrationState:
    """Spotlight 계획 수립 노드 - Query + Mutation 도구 사용

    Spotlight 모드는 독립적인 회의 관리에 특화되어:
    - Query + Mutation 도구 모두 사용
    - build_spotlight_system_prompt 사용
    - user_context를 컨텍스트로 활용

    Contract:
        reads: messages, retry_count, planning_context, tool_results, user_context, skip_planning, hitl_status
        writes: plan, need_tools, can_answer, selected_tool, tool_category, tool_args
        side-effects: LLM API 호출
        failures: PLANNING_FAILED -> 기본 계획 반환
    """
    logger.info("Planning 단계 진입")

    messages = state.get("messages", [])
    query = extract_last_human_query(messages)
    tool_results = state.get("tool_results", "")
    retry_count = state.get("retry_count", 0)

    # skip_planning 처리 (HITL 응답 시)
    if state.get("skip_planning") and state.get("plan"):
        logger.info("Planning 단계 스킵: 기존 plan 사용")
        logger.info(f"hitl_status 보존: {state.get('hitl_status')}")
        return SpotlightOrchestrationState(
            plan=state.get("plan", ""),
            need_tools=state.get("need_tools", False),
            can_answer=state.get("can_answer", True),
            missing_requirements=state.get("missing_requirements", []),
            selected_tool=state.get("selected_tool"),
            tool_category=state.get("tool_category"),
            tool_args=state.get("tool_args", {}),
            # HITL 상태 보존
            hitl_status=state.get("hitl_status"),
        )

    if retry_count >= PLANNING_MAX_RETRY:
        logger.warning("Planning 재시도 제한 도달, generator로 폴백")
        return SpotlightOrchestrationState(
            plan="재시도 제한 도달",
            need_tools=False,
            can_answer=True,
            selected_tool=None,
            tool_category=None,
            tool_args={},
        )

    if tool_results and any(marker in tool_results for marker in MUTATION_SUCCESS_MARKERS):
        logger.info("Mutation 도구 결과 확인 → 바로 응답")
        return SpotlightOrchestrationState(
            plan="도구 결과 기반 응답",
            need_tools=False,
            can_answer=True,
            selected_tool=None,
            tool_category=None,
            tool_args={},
        )

    if tool_results and "[MIT Search 결과" in tool_results:
        if detect_composite_query(query) and not is_subquery(query):
            logger.info("복합 쿼리 감지 → 다음 단계 replanning")
            return SpotlightOrchestrationState(
                plan="복합 쿼리 다음 단계",
                need_tools=True,
                can_answer=False,
                next_subquery=extract_next_step_query(query),
                retry_count=retry_count + 1,
            )

        logger.info("MIT Search 결과 확인 → 바로 응답")
        return SpotlightOrchestrationState(
            plan="검색 결과 기반 응답",
            need_tools=False,
            can_answer=True,
            selected_tool=None,
            tool_category=None,
            tool_args={},
        )

    # Spotlight는 모든 도구 사용 (Query + Mutation)
    langchain_tools = get_all_tools()
    logger.info(f"Spotlight mode, tools count: {len(langchain_tools)}")

    # bind_tools 적용
    llm = get_planner_llm()
    llm_with_tools = llm.bind_tools(langchain_tools)

    # Spotlight 시스템 프롬프트
    user_context = state.get("user_context", {})
    system_prompt = build_spotlight_system_prompt(user_context)

    # 컨텍스트가 있으면 시스템 프롬프트에 추가 (tool_results는 ToolMessage로 message history에 포함됨)
    planning_context = state.get("planning_context", "")
    if planning_context:
        system_prompt += f"\n\n[컨텍스트]\n{planning_context}"

    # 메시지 구성 (윈도잉 + orphan ToolMessage 필터링, HumanMessage는 window에 이미 포함)
    chat_messages = build_planner_chat_messages(system_prompt, messages)

    try:
        # 진단 로깅: LLM에 전송되는 도구 정보
        logger.info(f"Tools being sent to LLM: {[t.name for t in langchain_tools]}")
        logger.debug(f"Tool schemas: {[t.args_schema.schema() if t.args_schema else None for t in langchain_tools]}")

        # LLM 호출 (bind_tools 적용된 모델)
        response: AIMessage = await llm_with_tools.ainvoke(chat_messages)

        # ReAct Thought 캡처
        thought = response.content or ""
        if thought:
            logger.info(f"[ReAct Thought] {thought[:200]}")

        # 진단 로깅: LLM 응답 분석
        logger.info(f"LLM response type: {type(response).__name__}")
        logger.info(f"Has tool_calls: {bool(response.tool_calls)}")
        if response.tool_calls:
            logger.info(f"tool_calls content: {response.tool_calls}")
        else:
            logger.info(f"Response content (first 200 chars): {str(response.content)[:200]}")

        # tool_calls 파싱
        if response.tool_calls:
            first_call = response.tool_calls[0]
            tool_name = first_call["name"]
            tool_args = first_call.get("args", {})

            tool_category = get_tool_category(tool_name) or "query"

            logger.info(f"[ReAct Action] 도구 선택: {tool_name}")
            logger.info(f"도구 인자: {tool_args}")
            logger.info(f"도구 카테고리: {tool_category}")

            thought_summary = thought[:100] if thought else ""
            plan_text = f"[Thought] {thought_summary}\n[Action] {tool_name}" if thought_summary else f"도구 실행: {tool_name}"

            new_retry_count = retry_count + 1 if tool_results else retry_count
            return SpotlightOrchestrationState(
                messages=[response],
                selected_tool=tool_name,
                tool_args=tool_args,
                tool_category=tool_category,
                need_tools=False,
                can_answer=True,
                plan=plan_text,
                missing_requirements=[],
                retry_count=new_retry_count,
            )
        else:
            # 도구 없이 직접 응답
            logger.info("[ReAct] 도구 없이 직접 응답")
            logger.info(f"응답 내용: {response.content[:100]}..." if response.content else "응답 없음")

            return SpotlightOrchestrationState(
                can_answer=True,
                need_tools=False,
                plan=f"[Thought] {thought[:100]}" if thought else "직접 응답",
                selected_tool=None,
                tool_category=None,
                tool_args={},
            )

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")
        return SpotlightOrchestrationState(
            plan="질문 분석 중 오류 발생",
            need_tools=False,
            can_answer=True,
            missing_requirements=["query_analysis_error"],
            selected_tool=None,
            tool_category=None,
            tool_args={},
        )
