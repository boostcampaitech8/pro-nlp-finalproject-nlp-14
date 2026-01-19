import logging

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.graph.orchestrator.state import GraphState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


def generate_response(state: GraphState):
    """LLM으로 최종 응답을 생성하는 노드."""
    logger.info("최종 응답 생성 단계 진입")

    query = state["query"]
    plan = state["plan"]
    # tool_info가 None일 경우를 대비해 빈 문자열 처리
    tool_info = state.get("toolcalls", "") or "도구 사용 안 함"

    # HyperCLOVA X는 System Message(역할)와 Human Message(입력)를 분리하는 것이 좋습니다.
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 사용자의 질문에 대해 계획과 도구 결과를 바탕으로 친절하고 정확하게 답변하는 AI 비서입니다.",
            ),
            (
                "human",
                (
                    "다음 정보를 바탕으로 최종 답변을 작성해주세요.\n\n"
                    "질문: {query}\n"
                    "계획: {plan}\n"
                    "도구 정보: {tool_info}"
                ),
            ),
        ]
    )

    # LCEL 체인 구성 (Prompt -> LLM)
    chain = prompt | llm

    result = chain.invoke(
        {
            "query": query,
            "plan": plan,
            "tool_info": tool_info,
        }
    )

    return {"response": result.content}
