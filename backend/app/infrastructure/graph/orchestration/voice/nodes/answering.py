"""Voice Answering Node - 항상 voice 채널 사용"""

import logging
from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage

from app.infrastructure.graph.integration.llm import get_answer_generator_llm
from app.infrastructure.graph.orchestration.shared.message_utils import (
    build_generator_chat_messages,
)
from app.prompt.v1.orchestration.answering import (
    ChannelType,
    build_generator_system_prompt,
    build_system_prompt_for_guide,
)

from ..state import VoiceOrchestrationState

logger = logging.getLogger("Voice AgentLogger")


async def generate_answer(state: VoiceOrchestrationState):
    """Voice 최종 응답 생성 노드 - 항상 voice 채널 사용

    Contract:
        reads: messages, additional_context, planning_context, simple_router_output
        writes: response
        side-effects: LLM API 호출
    """
    logger.info("Voice 최종 응답 생성 단계 진입")

    messages = state.get("messages", [])
    additional_context = state.get("additional_context", "")
    planning_context = state.get("planning_context", "")
    simple_router_output = state.get("simple_router_output", {}) or {}
    simple_category = simple_router_output.get("category")

    # Voice는 항상 VOICE 채널
    channel = ChannelType.VOICE
    KST = timezone(timedelta(hours=9))
    current_time = datetime.now(KST).isoformat()
    logger.info(f"Voice mode, channel: {channel}")

    # 시스템 프롬프트 선택 (guide vs 일반)
    if simple_category == "guide":
        logger.info("가이드 요청: 전용 프롬프트 사용")
        system_prompt = build_system_prompt_for_guide(
            channel=channel,
            conversation_history="없음",
            meeting_context=planning_context or "없음",
            additional_context=additional_context or "없음",
        )
    else:
        system_prompt = build_generator_system_prompt(
            channel=channel,
            meeting_context=planning_context or "없음",
            additional_context=additional_context or "없음",
            current_time=current_time,
        )

    # messages 배열 기반으로 chat_messages 구성
    chat_messages = build_generator_chat_messages(
        system_prompt=system_prompt,
        messages=messages,
    )

    llm = get_answer_generator_llm()

    # 스트리밍으로 응답 생성
    response_chunks = []
    async for chunk in llm.astream(chat_messages):
        chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
        response_chunks.append(chunk_text)

    response_text = "".join(response_chunks)
    logger.info(f"Voice 응답 생성 완료 (길이: {len(response_text)})")

    return VoiceOrchestrationState(response=response_text, messages=[AIMessage(content=response_text)])
