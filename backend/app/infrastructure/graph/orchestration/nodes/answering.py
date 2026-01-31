import logging

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_answer_generator_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


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
    plan = state.get("plan", "")
    can_answer = state.get("can_answer")
    missing_requirements = state.get("missing_requirements", [])
    tool_results = state.get("tool_results", "")
    additional_context = state.get("additional_context", "")
    
    logger.info(f"tool_results 확인: {bool(tool_results)}, 길이: {len(tool_results) if tool_results else 0}")
    
    print("\n" + "=" * 50)
    print("답변:")
    print("=" * 50)
    
    # planner가 답변 불가로 판단한 경우
    if can_answer is False:
        missing_text = (
            "\n필요한 요소: " + ", ".join(missing_requirements)
            if missing_requirements
            else ""
        )
        response_text = (
            "현재 워크플로우의 도구( mit_search )로는 요청을 처리할 수 없습니다."
            + missing_text
        )
        print(response_text, flush=True)
        print("=" * 50)
        return OrchestrationState(response=response_text)

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
                    """당신은 사용자의 질문에 대해 계획과 도구 실행 결과를 바탕으로 정확하게 답변하는 AI 비서입니다.
중요 규칙:
1. 도구 결과에 없는 사실을 추측하거나 외부 출처(웹/검색엔진)를 언급하지 마세요.
2. 검색 결과가 없으면 명확하게 "정보를 찾을 수 없습니다"라고 답변하세요.
3. 특정 사람이름 검색 후 결과가 없으면: "신수효에 대한 정보를 찾을 수 없습니다. 혹시 이름을 다시 확인해주시겠어요?"
4. 일반 지식이나 추측으로 답변하지 마세요. 도구 결과만 신뢰하세요."""
                ),
                (
                    "human",
                    (
                        "다음 정보를 바탕으로 최종 답변을 작성해주세요.\n\n"
                        "질문: {query}\n"
                        "계획: {plan}\n"
                        "도구 실행 결과: {tool_results}\n\n"
                        "추가 컨텍스트:\n{additional_context}\n\n"
                        "도구 실행 결과를 정확하게 활용하여 사용자 질문에 답변해주세요. 결과가 없으면 명확하게 '정보를 찾을 수 없습니다'라고 답변하세요."
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
                        "추가 컨텍스트:\n{additional_context}\n\n"
                        "추가 정보 없이 답변 가능한 질문입니다. 친절하게 답변해주세요."
                    ),
                ),
            ]
        )

    chain = prompt | get_answer_generator_llm()

    # 스트리밍으로 응답 생성 및 출력
    response_chunks = []
    async for chunk in chain.astream(
        {
            "query": query,
            "plan": plan,
            "tool_results": tool_results or "없음",
            "additional_context": additional_context or "없음",
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

