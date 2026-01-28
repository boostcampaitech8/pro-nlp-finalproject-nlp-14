import logging

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_generator_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


async def generate_answer(state: OrchestrationState):
    """최종 응답을 생성하는 노드

    Contract:
        reads: messages, plan, tool_results
        writes: response
        side-effects: LLM API 호출
    """
    logger.info("최종 응답 생성 단계 진입")

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    plan = state.get("plan", "")
    tool_results = state.get("tool_results", "")

    logger.info(f"도구 결과 포함 여부: {bool(tool_results)}")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 사용자의 질문에 대해 계획과 도구 실행 결과를 바탕으로 친절하고 정확하게 답변하는 AI 비서입니다.",
            ),
            (
                "human",
                (
                    "다음 정보를 바탕으로 최종 답변을 작성해주세요.\n\n"
                    "질문: {query}\n"
                    "계획: {plan}\n"
                    "도구 실행 결과: {tool_results}\n\n"
                    "사용자 질문에 정확하고 친절하게 답변해주세요."
                ),
            ),
        ]
    )

    chain = prompt | get_generator_llm()

    response_chunks = []
    async for chunk in chain.astream(
        {
            "query": query,
            "plan": plan,
            "tool_results": tool_results or "없음",
        }
    ):
        chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
        response_chunks.append(chunk_text)

    response_text = "".join(response_chunks)
    logger.info(f"응답 생성 완료 (길이: {len(response_text)}자)")

    return OrchestrationState(response=response_text)

