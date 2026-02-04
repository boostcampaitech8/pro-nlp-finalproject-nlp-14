import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_answer_generator_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState
from app.prompts.v1.orchestration.answering import (
    ChannelType,
    build_system_prompt_with_tools,
    build_system_prompt_without_tools,
    build_user_prompt_with_tools,
    build_user_prompt_without_tools,
)

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


def build_conversation_history(messages: list) -> str:
    """이전 대화 히스토리를 문자열로 변환 (멀티턴 지원)"""
    if len(messages) <= 1:
        return ""

    history_parts = []
    for msg in messages[:-1]:  # 마지막 메시지(현재 질문) 제외
        if isinstance(msg, HumanMessage):
            history_parts.append(f"사용자: {msg.content}")
        elif isinstance(msg, AIMessage):
            # AI 응답이 너무 길면 요약
            content = msg.content
            if len(content) > 500:
                content = content[:500] + "..."
            history_parts.append(f"AI: {content}")

    return "\n".join(history_parts)


async def generate_answer(state: OrchestrationState):
    """최종 응답을 생성하는 노드

    Contract:
        reads: messages, plan, tool_results, is_simple_query, response, channel
        writes: response (필요한 경우만)
        side-effects: LLM API 호출, stdout 출력 (스트리밍)
    """
    logger.info("최종 응답 생성 단계 진입")

    # 간단한 쿼리는 simple_router_output을 보고 응답 생성
    if state.get("is_simple_query", False):
        simple_router_output = state.get("simple_router_output", {})
        category = simple_router_output.get("category", "other")
        simple_response = simple_router_output.get("simple_response")

        messages = state.get('messages', [])
        query = messages[-1].content if messages else ""

        logger.info(f"간단한 쿼리 응답 생성: category={category}, query={query[:50]}...")

        # 카테고리별 프롬프트 설정
        if simple_response:
            # simple_router에서 제안한 응답이 있으면 참고
            prompt = ChatPromptTemplate.from_messages([
                ("system", "당신은 친절한 AI 비서입니다. 사용자의 질문에 자연스럽고 친근하게 답변하세요."),
                ("human", "사용자 질문: {query}\n\n제안 응답: {suggested_response}\n\n위 제안을 참고하여 자연스럽게 답변하세요.")
            ])
            input_data = {"query": query, "suggested_response": simple_response}
        else:
            # 제안 응답이 없으면 카테고리 기반 응답
            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "당신은 친절한 AI 비서입니다.\n"
                 "사용자의 인사나 감정 표현에 자연스럽고 친근하게 응답하세요.\n"
                 "간단하고 따뜻한 한두 문장으로 답변하세요."),
                ("human", "{query}")
            ])
            input_data = {"query": query}

        chain = prompt | get_answer_generator_llm()

        # 스트리밍으로 응답 생성
        response_chunks = []
        async for chunk in chain.astream(input_data):
            chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
            response_chunks.append(chunk_text)

        final_response = "".join(response_chunks)
        logger.info(f"간단한 쿼리 응답 생성 완료 (길이: {len(final_response)}자)")

        return {"response": final_response}

    messages = state.get('messages', [])
    logger.info(f"[DEBUG] messages 개수: {len(messages)}")
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        content_preview = msg.content[:50] if msg.content else ""
        logger.info(f"[DEBUG] messages[{i}]: {msg_type} - {content_preview}...")

    query = messages[-1].content if messages else ""
    conversation_history = build_conversation_history(messages)
    logger.info(f"[DEBUG] conversation_history 길이: {len(conversation_history)}자")
    tool_results = state.get("tool_results", "")
    additional_context = state.get("additional_context", "")
    planning_context = state.get("planning_context", "")  # L0 회의 대화 + L1 토픽
    plan = state.get("plan", "")
    channel = state.get("channel", ChannelType.VOICE)  # 기본값: 음성

    logger.info(f"tool_results 확인: {bool(tool_results)}, 길이: {len(tool_results) if tool_results else 0}")
    logger.info(f"planning_context 길이: {len(planning_context)}자")
    logger.info(f"channel: {channel}")

    # tool_results가 있으면 추가 context로 활용
    if tool_results and tool_results.strip():
        logger.info(f"도구 결과 포함 여부: {bool(tool_results)}")

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

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt),
        ])
        input_data = {}  # 이미 포맷팅됨
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
            ("system", system_prompt),
            ("human", user_prompt),
        ])
        input_data = {}  # 이미 포맷팅됨

    chain = prompt | get_answer_generator_llm()

    # 멀티턴 로깅
    if conversation_history:
        logger.info(f"이전 대화 포함: {len(conversation_history)}자")

    # 스트리밍으로 응답 생성
    response_chunks = []

    async for chunk in chain.astream(input_data):
        chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
        response_chunks.append(chunk_text)

    response_text = "".join(response_chunks)
    logger.info(f"응답 생성 완료 (길이: {len(response_text)}자)")

    return OrchestrationState(response=response_text)

