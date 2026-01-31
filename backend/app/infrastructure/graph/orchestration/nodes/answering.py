import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_generator_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

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
        reads: messages, plan, tool_results
        writes: response
        side-effects: LLM API 호출, stdout 출력 (스트리밍)
    """
    logger.info("최종 응답 생성 단계 진입")

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    conversation_history = build_conversation_history(messages)
    plan = state.get("plan", "")
    tool_results = state.get("tool_results", "")
    additional_context = state.get("additional_context", "")
    
    logger.info(f"tool_results 확인: {bool(tool_results)}, 길이: {len(tool_results) if tool_results else 0}")
    
    print("\n" + "=" * 50)
    print("답변:")
    print("=" * 50)
    
    # tool_results가 있으면 추가 context로 활용
    if tool_results and tool_results.strip():
        logger.info(f"도구 결과 포함 여부: {bool(tool_results)}")

        # 도구 결과가 명확할 때는 그대로 출력 (환각 방지)
        if "[MIT Search 결과" in tool_results:
            logger.info("MIT Search 결과를 직접 출력합니다.")
            print(tool_results.strip(), flush=True)
            print("=" * 50)
            return OrchestrationState(response=tool_results.strip())

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 사용자의 질문에 대해 계획과 도구 실행 결과를 바탕으로 정확하게 답변하는 AI 비서입니다."
                    " 이전 대화 맥락을 참고하여 일관된 답변을 제공하세요."
                    " 도구 결과에 없는 사실을 추측하거나 외부 출처(웹/검색엔진)를 언급하지 마세요.",
                ),
                (
                    "human",
                    (
                        "다음 정보를 바탕으로 최종 답변을 작성해주세요.\n\n"
                        "## 이전 대화\n{conversation_history}\n\n"
                        "## 현재 질문\n{query}\n\n"
                        "## 계획\n{plan}\n\n"
                        "## 도구 실행 결과\n{tool_results}\n\n"
                        "## 추가 컨텍스트\n{additional_context}\n\n"
                        "이전 대화 맥락과 도구 실행 결과를 활용하여 사용자 질문에 정확하게 답변해주세요."
                    ),
                ),
            ]
        )
    else:
        logger.info("도구 없이 직접 응답 생성")
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "당신은 사용자의 질문에 친절하고 정확하게 답변하는 AI 비서입니다."
                    " 이전 대화 맥락을 참고하여 일관된 답변을 제공하세요.",
                ),
                (
                    "human",
                    (
                        "다음 질문에 답변해주세요.\n\n"
                        "## 이전 대화\n{conversation_history}\n\n"
                        "## 현재 질문\n{query}\n\n"
                        "## 계획\n{plan}\n\n"
                        "## 추가 컨텍스트\n{additional_context}\n\n"
                        "이전 대화 맥락을 참고하여 친절하게 답변해주세요."
                    ),
                ),
            ]
        )

    chain = prompt | get_generator_llm()

    # 멀티턴 로깅
    if conversation_history:
        logger.info(f"이전 대화 포함: {len(conversation_history)}자")

    # 스트리밍으로 응답 생성 및 출력
    response_chunks = []
    async for chunk in chain.astream(
        {
            "query": query,
            "plan": plan,
            "tool_results": tool_results or "없음",
            "additional_context": additional_context or "없음",
            "conversation_history": conversation_history or "없음",
        }
    ):
        chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
        response_chunks.append(chunk_text)
        print(chunk_text, end="", flush=True)
    
    print()  # 줄바꿈
    print("=" * 50)
    
    response_text = "".join(response_chunks)
    logger.info(f"응답 생성 완료 (길이: {len(response_text)}자)")
    
    return OrchestrationState(response=response_text)

