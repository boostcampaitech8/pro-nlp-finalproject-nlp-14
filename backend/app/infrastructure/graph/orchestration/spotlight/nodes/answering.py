import logging

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

from ..state import SpotlightOrchestrationState

logger = logging.getLogger("AgentLogger")


async def generate_answer(state: SpotlightOrchestrationState):
    """최종 응답을 생성하는 노드

        Contract:
        reads: messages, tool_results, tool_execution_status,
               additional_context, planning_context, simple_router_output
        writes: response
        side-effects: LLM API 호출, stdout 출력 (스트리밍)
    """
    logger.info("최종 응답 생성 단계 진입")

    # Cancel 시 LLM 호출 없이 직접 반환
    if state.get("tool_execution_status") == "cancelled":
        cancel_msg = state.get("tool_results", "").strip() or "작업이 취소되었습니다."
        logger.info(f"Cancel 감지 → LLM 호출 없이 직접 반환: {cancel_msg}")
        return SpotlightOrchestrationState(response=cancel_msg, messages=[AIMessage(content=cancel_msg)])

    messages = state.get('messages', [])
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("checkpointer 병합 후 messages 개수: %d", len(messages))
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            content_preview = content[:50] if content else ""
            logger.debug("messages[%d]: %s - %s...", i, msg_type, content_preview)

    tool_results = state.get("tool_results", "")
    additional_context = state.get("additional_context", "")
    planning_context = state.get("planning_context", "")
    simple_router_output = state.get("simple_router_output", {}) or {}
    simple_category = simple_router_output.get("category")
    user_context = state.get("user_context", {}) or {}
    current_time = user_context.get("current_time", "")

    # Mutation 성공 시 LLM 호출 없이 결과를 직접 반환
    mutation_success_markers = [
        "성공적으로 생성", "생성되었습니다", "생성 완료",
        "성공적으로 수정", "수정되었습니다", "수정 완료",
        "성공적으로 삭제", "삭제되었습니다", "삭제 완료",
    ]
    has_mutation_result = tool_results and any(marker in tool_results for marker in mutation_success_markers)

    if has_mutation_result:
        mutation_message = tool_results
        for marker in mutation_success_markers:
            pos = tool_results.rfind(marker)
            if pos != -1:
                before = tool_results[:pos]
                brace_pos = before.rfind('}')
                if brace_pos != -1:
                    mutation_message = tool_results[brace_pos + 1:].strip()
                break
        logger.info(f"Mutation 성공 결과 직접 반환: {mutation_message}")
        return SpotlightOrchestrationState(response=mutation_message, messages=[AIMessage(content=mutation_message)])

    logger.info(f"tool_results 확인: {bool(tool_results)}, 길이: {len(tool_results) if tool_results else 0}")
    logger.info(f"planning_context 길이: {len(planning_context)}자")

    # Spotlight는 항상 TEXT 채널 사용
    channel = ChannelType.TEXT
    logger.info(f"Spotlight mode, channel: {channel}")

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
    logger.info(f"응답 생성 완료 (길이: {len(response_text)}자)")

    return SpotlightOrchestrationState(response=response_text, messages=[AIMessage(content=response_text)])
