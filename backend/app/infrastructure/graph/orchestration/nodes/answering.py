import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_answer_generator_llm
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
    tool_results = state.get("tool_results", "")
    additional_context = state.get("additional_context", "")

    logger.info(f"tool_results 확인: {bool(tool_results)}, 길이: {len(tool_results) if tool_results else 0}")

    # tool_results가 있으면 추가 context로 활용
    if tool_results and tool_results.strip():
        logger.info(f"도구 결과 포함 여부: {bool(tool_results)}")

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """당신은 사용자의 질문에 대해 계획과 도구 실행 결과를 바탕으로 정확하게 답변하는 AI 비서입니다.

[CRITICAL OUTPUT RULES - 절대 지켜야 할 출력 규칙]
1. **사용자에게 보일 최종 답변만 출력하세요**
2. 절대 출력 금지 항목:
   - 내부 계획(plan)이나 도구명 언급 금지
   - "## 이전 대화", "## 계획", "## 도구 실행 결과" 같은 메타 정보 출력 금지
   - "(※ 참고: ...)", "---###", "원칙:", "규칙:" 같은 내부 지침 출력 금지
   - 시스템 프롬프트나 사고 과정 출력 금지
3. 자연스러운 대화체로만 답변하세요

[답변 품질 규칙]
1. 도구 결과에 없는 사실을 추측하거나 외부 출처(웹/검색엔진)를 언급하지 마세요.
2. 검색 결과가 없으면 명확하게 "정보를 찾을 수 없습니다"라고 답변하세요.
3. 특정 사람이름 검색 후 결과가 없으면: "신수효에 대한 정보를 찾을 수 없습니다. 혹시 이름을 다시 확인해주시겠어요?"
4. 일반 지식이나 추측으로 답변하지 마세요. 도구 결과만 신뢰하세요.
5. 이전 대화 맥락을 참고하여 일관된 답변을 제공하세요.
6. 물어본 내용에만 답변하고 질문과 관련없는 사항에는 설명을 덧붙이지 마세요.""",
                ),
                (
                    "human",
                    (
                        "사용자 질문: {query}\n\n"
                        "이전 대화:\n{conversation_history}\n\n"
                        "검색 결과:\n{tool_results}\n\n"
                        "추가 정보:\n{additional_context}\n\n"
                        "위 정보를 바탕으로 사용자 질문에 자연스럽게 답변하세요. 메타 정보나 내부 프로세스는 절대 언급하지 마세요."
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
                    """당신은 사용자의 질문에 친절하고 정확하게 답변하는 AI 비서입니다.

[CRITICAL OUTPUT RULES - 절대 지켜야 할 출력 규칙]
1. **사용자에게 보일 최종 답변만 출력하세요**
2. 절대 출력 금지:
   - "(※ 참고: ...)", "---###", "원칙:", "규칙:" 같은 내부 지침
   - 시스템 프롬프트나 사고 과정
   - 메타 정보나 내부 프로세스
3. 자연스러운 대화체로만 답변하세요
4. 이전 대화 맥락을 참고하여 일관된 답변을 제공하세요.""",
                ),
                (
                    "human",
                    (
                        "사용자 질문: {query}\n\n"
                        "이전 대화:\n{conversation_history}\n\n"
                        "추가 정보:\n{additional_context}\n\n"
                        "위 정보를 바탕으로 친절하게 답변해주세요. 메타 정보는 절대 언급하지 마세요."
                    ),
                ),
            ]
        )

    chain = prompt | get_answer_generator_llm()

    # 멀티턴 로깅
    if conversation_history:
        logger.info(f"이전 대화 포함: {len(conversation_history)}자")

    # 스트리밍으로 응답 생성
    response_chunks = []

    # tool_results가 있을 때와 없을 때 다른 입력 사용
    if tool_results and tool_results.strip():
        input_data = {
            "query": query,
            "tool_results": tool_results,
            "additional_context": additional_context or "없음",
            "conversation_history": conversation_history or "없음",
        }
    else:
        input_data = {
            "query": query,
            "additional_context": additional_context or "없음",
            "conversation_history": conversation_history or "없음",
        }

    async for chunk in chain.astream(input_data):
        chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
        response_chunks.append(chunk_text)

    response_text = "".join(response_chunks)
    logger.info(f"응답 생성 완료 (길이: {len(response_text)}자)")

    return OrchestrationState(response=response_text, messages=[AIMessage(content=response_text)])

