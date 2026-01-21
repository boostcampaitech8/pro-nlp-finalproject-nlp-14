import logging

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


def generate_response(state: OrchestrationState):
    """LLM으로 최종 응답을 생성하는 노드."""
    logger.info("최종 응답 생성 단계 진입")

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    plan = state.get("plan", "")
    tool_results = state.get("tool_results", "")
    
    # tool_results가 있으면 추가 context로 활용
    if tool_results:
        logger.info("도구 실행 결과를 포함하여 응답 생성")
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
                        "도구 실행 결과를 활용하여 사용자 질문에 정확하게 답변해주세요."
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
                    "당신은 사용자의 질문에 친절하고 정확하게 답변하는 AI 비서입니다.",
                ),
                (
                    "human",
                    (
                        "다음 질문에 답변해주세요.\n\n"
                        "질문: {query}\n"
                        "계획: {plan}\n\n"
                        "추가 정보 없이 답변 가능한 질문입니다. 친절하게 답변해주세요."
                    ),
                ),
            ]
        )

    chain = prompt | llm

    result = chain.invoke(
        {
            "query": query,
            "plan": plan,
            "tool_results": tool_results or "없음",
        }
    )

    response_text = result.content if hasattr(result, "content") else str(result)
    logger.info(f"생성된 응답: {response_text[:100]}...")

    return {"response": response_text}

