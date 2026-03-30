"""Voice Planning Node - Query 도구만 사용"""

import logging
from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage

# 공유 도구 레지스트리에서 Query 도구만 가져오기
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
    get_tool_category,
    get_voice_tools,
)
from app.prompt.v1.orchestration.voice.planning import build_voice_system_prompt

from ..state import VoiceOrchestrationState

logger = logging.getLogger(__name__)


async def create_plan(state: VoiceOrchestrationState) -> VoiceOrchestrationState:
    """Voice 계획 수립 노드 - Query 도구만 사용

    Voice 모드는 회의 중 실시간 질의응답에 특화되어:
    - Query 도구만 사용 (MIT Search, 회의/팀 조회)
    - build_voice_system_prompt 사용
    - meeting_id를 컨텍스트로 활용

    Contract:
        reads: messages, retry_count, planning_context, tool_results, meeting_id
        writes: plan, need_tools, can_answer, selected_tool, tool_category, tool_args
        side-effects: LLM API 호출
        failures: PLANNING_FAILED -> 기본 계획 반환
    """
    logger.info("Voice Planning 단계 진입")

    messages = state.get("messages", [])
    query = extract_last_human_query(messages)
    meeting_id = state.get("meeting_id", "unknown")
    tool_results = state.get("tool_results", "")
    retry_count = state.get("retry_count", 0)

    if retry_count >= PLANNING_MAX_RETRY:
        logger.warning("Planning 재시도 제한 도달, generator로 폴백")
        return VoiceOrchestrationState(
            plan="재시도 제한 도달",
            need_tools=False,
            can_answer=True,
            selected_tool=None,
            tool_category=None,
            tool_args={},
        )

    if tool_results and any(marker in tool_results for marker in MUTATION_SUCCESS_MARKERS):
        logger.info("Mutation 도구 결과 확인 → 바로 응답")
        return VoiceOrchestrationState(
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
            return VoiceOrchestrationState(
                plan="복합 쿼리 다음 단계",
                need_tools=True,
                can_answer=False,
                next_subquery=extract_next_step_query(query),
                retry_count=retry_count + 1,
            )

        logger.info("MIT Search 결과 확인 → 바로 응답")
        return VoiceOrchestrationState(
            plan="검색 결과 기반 응답",
            need_tools=False,
            can_answer=True,
            selected_tool=None,
            tool_category=None,
            tool_args={},
        )

    # Voice 전용 도구만 가져오기 (모드 필터링 적용)
    langchain_tools = get_voice_tools()
    logger.info(f"Voice mode, tools count: {len(langchain_tools)}")

    # bind_tools 적용
    llm = get_planner_llm()
    llm_with_tools = llm.bind_tools(langchain_tools)

    # Voice 시스템 프롬프트 (팀 컨텍스트 포함)
    KST = timezone(timedelta(hours=9))
    current_time = datetime.now(KST).isoformat()
    team_context = state.get("team_context")
    system_prompt = build_voice_system_prompt(
        meeting_id, current_time=current_time, team_context=team_context
    )

    # 컨텍스트가 있으면 시스템 프롬프트에 추가 (tool_results는 ToolMessage로 message history에 포함됨)
    planning_context = state.get("planning_context", "")
    if planning_context:
        system_prompt += f"\n\n[컨텍스트]\n{planning_context}"

    # 메시지 구성 (윈도잉 + orphan ToolMessage 필터링, HumanMessage는 window에 이미 포함)
    chat_messages = build_planner_chat_messages(system_prompt, messages)

    try:
        logger.info(f"Tools being sent to LLM: {[t.name for t in langchain_tools]}")

        # LLM 호출
        response: AIMessage = await llm_with_tools.ainvoke(chat_messages)

        # ReAct Thought 캡처
        thought = response.content or ""
        if thought:
            logger.info(f"[ReAct Thought] {thought[:200]}")

        logger.info(f"LLM response type: {type(response).__name__}")
        logger.info(f"Has tool_calls: {bool(response.tool_calls)}")

        # tool_calls 파싱
        if response.tool_calls:
            first_call = response.tool_calls[0]
            tool_name = first_call["name"]
            tool_args = first_call.get("args", {})
            tool_category = get_tool_category(tool_name) or "query"

            logger.info(f"[ReAct Action] 도구 선택: {tool_name}")
            logger.info(f"도구 인자: {tool_args}")

            thought_summary = thought[:100] if thought else ""
            plan_text = f"[Thought] {thought_summary}\n[Action] {tool_name}" if thought_summary else f"도구 실행: {tool_name}"

            new_retry_count = retry_count + 1 if tool_results else retry_count
            return VoiceOrchestrationState(
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
            return VoiceOrchestrationState(
                can_answer=True,
                need_tools=False,
                plan=f"[Thought] {thought[:100]}" if thought else "직접 응답",
                selected_tool=None,
                tool_category=None,
                tool_args={},
            )

    except Exception as e:
        logger.error(f"Planning 실패: {e}", exc_info=True)
        # 실패 시 기본 응답
        return VoiceOrchestrationState(
            plan="오류 발생",
            need_tools=False,
            can_answer=True,
            response=f"죄송합니다. 요청을 처리하는 중 오류가 발생했습니다: {str(e)}",
        )
