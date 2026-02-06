"""Voice Planning Node - Query 도구만 사용"""

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# 공유 도구 레지스트리에서 Query 도구만 가져오기
import app.infrastructure.graph.orchestration.shared.tools  # noqa: F401
from app.infrastructure.graph.integration.llm import get_planner_llm_for_tools
from app.infrastructure.graph.orchestration.shared.tools.registry import (
    get_query_tools,
    get_tool_category,
)
from app.prompt.v1.orchestration.voice.planning import build_voice_system_prompt

from ..state import VoiceOrchestrationState

logger = logging.getLogger(__name__)

PLANNING_MAX_RETRY = 3
MUTATION_SUCCESS_MARKERS = [
    "생성되었습니다",
    "수정되었습니다",
    "삭제되었습니다",
    '"success": true',
    "'success': True",
]


def _is_subquery(query: str) -> bool:
    """Replanning에서 생성된 서브-쿼리인지 확인."""
    subquery_keywords = [
        "이전에 찾은",
        "그 담당자",
        "그 사람",
        "그 액션",
        "그 팀원",
        "그 팀",
        "그 결정",
        "찾은",
    ]
    return any(kw in query for kw in subquery_keywords)


def _detect_composite_query(query: str) -> bool:
    """복합 쿼리(여러 단계의 검색이 필요한 쿼리) 감지."""
    assignment_keywords = ["맡고 있는", "담당", "책임자", "담당자", "맡은"]
    team_keywords = ["팀원", "같은 팀", "팀에서", "팀의"]
    has_assignment = any(kw in query for kw in assignment_keywords)
    has_team = any(kw in query for kw in team_keywords)
    return has_assignment and has_team


def _extract_next_step_query(query: str) -> str:
    """Turn 1 결과를 바탕으로 Turn 2 서브-쿼리 생성."""
    if "팀원" in query:
        return "이전에 찾은 담당자와 같은 팀의 팀원은 누구인가?"
    if "같은 팀" in query or "팀에서" in query or "팀의" in query:
        return "이전에 찾은 담당자와 같은 팀의 팀원들은 누구인가?"
    return "이전에 찾은 담당자의 팀 정보는?"


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
    query = messages[-1].content if messages else ""
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
        if _detect_composite_query(query) and not _is_subquery(query):
            logger.info("복합 쿼리 감지 → 다음 단계 replanning")
            return VoiceOrchestrationState(
                plan="복합 쿼리 다음 단계",
                need_tools=True,
                can_answer=False,
                next_subquery=_extract_next_step_query(query),
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

    # Query 도구만 가져오기 (Voice 전용)
    langchain_tools = get_query_tools()
    logger.info(f"Voice mode, tools count: {len(langchain_tools)}")

    # bind_tools 적용
    llm = get_planner_llm_for_tools()
    llm_with_tools = llm.bind_tools(langchain_tools)

    # Voice 시스템 프롬프트
    system_prompt = build_voice_system_prompt(meeting_id)

    # 이전 도구 실행 결과를 컨텍스트에 포함
    planning_context = state.get("planning_context", "")
    if tool_results:
        if planning_context:
            planning_context = f"[이전 도구 실행 결과]\n{tool_results}\n\n{planning_context}"
        else:
            planning_context = f"[이전 도구 실행 결과]\n{tool_results}"
        logger.info(f"tool_results를 planning_context에 포함 (길이: {len(tool_results)})")

    # 컨텍스트가 있으면 시스템 프롬프트에 추가
    if planning_context:
        system_prompt += f"\n\n[컨텍스트]\n{planning_context}"

    # 메시지 구성
    chat_messages = [SystemMessage(content=system_prompt)]

    # 이전 대화 히스토리 포함 (최근 10개, 현재 메시지 제외)
    if len(messages) > 1:
        for msg in messages[-11:-1]:
            if msg.type == "human":
                chat_messages.append(HumanMessage(content=msg.content))
            else:
                chat_messages.append(AIMessage(content=msg.content))

    # 현재 메시지
    chat_messages.append(HumanMessage(content=query))

    try:
        logger.info(f"Tools being sent to LLM: {[t.name for t in langchain_tools]}")

        # LLM 호출
        response: AIMessage = await llm_with_tools.ainvoke(chat_messages)

        logger.info(f"LLM response type: {type(response).__name__}")
        logger.info(f"Has tool_calls: {bool(response.tool_calls)}")

        # tool_calls 파싱
        if response.tool_calls:
            first_call = response.tool_calls[0]
            tool_name = first_call["name"]
            tool_args = first_call.get("args", {})
            tool_category = get_tool_category(tool_name) or "query"

            logger.info(f"도구 선택됨: {tool_name}")
            logger.info(f"도구 인자: {tool_args}")

            new_retry_count = retry_count + 1 if tool_results else retry_count
            return VoiceOrchestrationState(
                messages=[response],
                selected_tool=tool_name,
                tool_args=tool_args,
                tool_category=tool_category,
                need_tools=False,
                can_answer=True,
                plan=f"도구 실행: {tool_name}",
                missing_requirements=[],
                retry_count=new_retry_count,
            )
        else:
            # 도구 없이 직접 응답
            logger.info("도구 없이 직접 응답")
            return VoiceOrchestrationState(
                messages=[response],
                response=response.content,
                can_answer=True,
                need_tools=False,
                plan="직접 응답",
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
