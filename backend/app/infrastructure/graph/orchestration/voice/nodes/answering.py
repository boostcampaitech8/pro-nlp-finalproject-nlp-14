"""Voice Answering Node - 항상 voice 채널 사용"""

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_answer_generator_llm
from app.prompt.v1.orchestration.answering import (
    ChannelType,
    build_system_prompt_with_tools,
    build_system_prompt_without_tools,
    build_user_prompt_with_tools,
    build_user_prompt_without_tools,
)

from ..state import VoiceOrchestrationState

logger = logging.getLogger("Voice AgentLogger")


def build_conversation_history(messages: list) -> str:
    """이전 대화 히스토리를 문자열로 변환"""
    if len(messages) <= 1:
        return ""

    history_parts = []
    for msg in messages[:-1]:  # 마지막 메시지(현재 질문) 제외
        if isinstance(msg, HumanMessage):
            history_parts.append(f"사용자: {msg.content}")
        elif isinstance(msg, AIMessage):
            content = msg.content
            if len(content) > 500:
                content = content[:500] + "..."
            history_parts.append(f"AI: {content}")

    return "\n".join(history_parts)


async def generate_answer(state: VoiceOrchestrationState):
    """Voice 최종 응답 생성 노드 - 항상 voice 채널 사용

    Contract:
        reads: messages, plan, tool_results, additional_context, planning_context
        writes: response
        side-effects: LLM API 호출
    """
    logger.info("Voice 최종 응답 생성 단계 진입")

    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""
    conversation_history = build_conversation_history(messages)
    tool_results = state.get("tool_results", "")
    additional_context = state.get("additional_context", "")
    planning_context = state.get("planning_context", "")
    plan = state.get("plan", "")

    # Voice는 항상 VOICE 채널
    channel = ChannelType.VOICE
    logger.info(f"Voice mode, channel: {channel}")

    # 프롬프트 생성
    if tool_results and tool_results.strip():
        logger.info(f"도구 결과 포함 응답 생성")
        system_prompt = build_system_prompt_with_tools(channel)
        user_prompt = build_user_prompt_with_tools(
            conversation_history=conversation_history or "없음",
            query=query,
            plan=plan or "없음",
            tool_results=tool_results,
            additional_context=additional_context or "없음",
            meeting_context=planning_context or "없음",
            channel=channel,
        )
    else:
        logger.info("도구 없이 직접 응답 생성")
        system_prompt = build_system_prompt_without_tools(channel)
        user_prompt = build_user_prompt_without_tools(
            conversation_history=conversation_history or "없음",
            query=query,
            plan=plan or "없음",
            additional_context=additional_context or "없음",
            meeting_context=planning_context or "없음",
            channel=channel,
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ])
    input_data = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }

    chain = prompt | get_answer_generator_llm()

    # 응답 생성
    response_chunks = []
    async for chunk in chain.astream(input_data):
        chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
        response_chunks.append(chunk_text)

    response_text = "".join(response_chunks)
    logger.info(f"Voice 응답 생성 완료 (길이: {len(response_text)})")

    return VoiceOrchestrationState(response=response_text, messages=[AIMessage(content=response_text)])
