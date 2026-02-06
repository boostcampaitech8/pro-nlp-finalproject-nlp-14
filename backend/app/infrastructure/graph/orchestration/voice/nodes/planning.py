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
    tool_results = state.get("tool_results", "")
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

            return VoiceOrchestrationState(
                messages=[response],
                selected_tool=tool_name,
                tool_args=tool_args,
                tool_category=tool_category,
                need_tools=False,
                can_answer=True,
                plan=f"도구 실행: {tool_name}",
                missing_requirements=[],
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


    # 이전 도구 실행 결과를 컨텍스트에 포함
    planning_context = state.get("planning_context", "")
    tool_results = state.get("tool_results", "")
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

            return VoiceOrchestrationState(
                messages=[response],
                selected_tool=tool_name,
                tool_args=tool_args,
                tool_category=tool_category,
                need_tools=False,
                can_answer=True,
                plan=f"도구 실행: {tool_name}",
                missing_requirements=[],
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
