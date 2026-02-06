import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_answer_generator_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState
from app.infrastructure.graph.orchestration.tools.registry import (
    InteractionMode,
    normalize_interaction_mode,
)
from app.prompt.v1.orchestration.answering import (
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
        reads: messages, plan, tool_results, is_simple_query, simple_router_output,
               additional_context, planning_context, channel
        writes: response
        side-effects: LLM API 호출, stdout 출력 (스트리밍)
    """
    logger.info("최종 응답 생성 단계 진입")

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
    # ✅ 안전 장치: Mutation 요청인데 도구가 실행되지 않은 경우 거부
    query_lower = query.lower()
    mutation_keywords = ["만들어", "생성", "추가", "등록", "수정", "변경", "삭제", "취소", "잡아"]
    meeting_keywords = ["회의", "미팅", "meeting"]
    is_mutation_request = any(kw in query_lower for kw in mutation_keywords)
    is_meeting_related = any(kw in query_lower for kw in meeting_keywords)

    # Mutation 도구 실행 결과 확인 (생성/수정/삭제 성공 메시지)
    mutation_success_markers = [
        "성공적으로 생성", "생성되었습니다", "생성 완료",
        "성공적으로 수정", "수정되었습니다", "수정 완료",
        "성공적으로 삭제", "삭제되었습니다", "삭제 완료",
        "created", "updated", "deleted"
    ]
    has_mutation_result = tool_results and any(marker in tool_results for marker in mutation_success_markers)

    # 회의 관련 mutation 요청인데 mutation 결과가 없으면 거부
    if is_mutation_request and is_meeting_related and not has_mutation_result:
        # tool_results가 조회 결과(팀 목록, 회의 목록)만 있는 경우는 허용 (다음 단계 진행 중)
        is_query_result_only = tool_results and ("teams" in tool_results or "meetings" in tool_results or "팀" in tool_results)

        if not is_query_result_only:
            logger.warning(f"Mutation 요청이지만 도구 실행 결과가 없음: {query}")
            # 도구 실행 없이 허위 응답 생성 방지
            response_text = "죄송합니다. 요청하신 작업을 처리하는 중 문제가 발생했습니다. 다시 한 번 시도해 주세요."
            return OrchestrationState(response=response_text, messages=[AIMessage(content=response_text)])

    logger.info(f"tool_results 확인: {bool(tool_results)}, 길이: {len(tool_results) if tool_results else 0}")
    logger.info(f"planning_context 길이: {len(planning_context)}자")
    # interaction_mode를 channel로 매핑
    interaction_mode = normalize_interaction_mode(state.get("interaction_mode", "voice"))
    channel = ChannelType.TEXT if interaction_mode == InteractionMode.SPOTLIGHT else ChannelType.VOICE
    logger.info(f"interaction_mode: {interaction_mode.value}, channel: {channel}")
    plan = state.get("plan", "")

    # 프롬프트 빌더 사용
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

    # 이미 포맷팅된 문자열에 포함된 JSON/중괄호가 변수로 해석되지 않도록 변수로 전달
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ])
    input_data = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }

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

    return OrchestrationState(response=response_text, messages=[AIMessage(content=response_text)])
