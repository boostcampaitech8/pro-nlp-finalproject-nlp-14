import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.config import MAX_RETRY
from app.infrastructure.graph.integration.llm import get_evaluator_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


class EvaluationOutput(BaseModel):
    evaluation: str = Field(description="도구 실행 결과에 대한 평가")
    status: str = Field(description="다음 단계: 'success'(완료), 'retry'(재실행), 'replanning'(재계획)")
    reason: str = Field(description="해당 status를 선택한 이유")


async def evaluate_result(state: OrchestrationState) -> OrchestrationState:
    """MIT-Tools 실행 결과를 평가하는 노드

    Contract:
        reads: messages, plan, tool_results, retry_count
        writes: evaluation, evaluation_status, evaluation_reason, retry_count
        side-effects: LLM API 호출
        failures: EVALUATION_FAILED -> 강제 success 처리

    평가 결과 status:
        - success: 충분한 정보 획득, 최종 응답 생성 가능
        - retry: 도구 실행 실패나 불충분한 결과, 같은 도구 재실행 필요
        - replanning: 계획이 잘못됨, 다른 접근 방법 필요
    """
    logger.info("Evaluator 단계 진입")

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    plan = state.get('plan', '')
    tool_results = state.get('tool_results', '')
    retry_count = state.get('retry_count', 0)

    # 무한 루프 방지: MAX_RETRY 이상 재시도 시 강제로 success 처리
    if retry_count >= MAX_RETRY:
        logger.warning(f"최대 재시도 횟수({MAX_RETRY}) 도달 - 강제 완료 처리")
        return OrchestrationState(
            evaluation="최대 재시도 횟수 도달",
            evaluation_status="success",
            evaluation_reason="더 이상 재시도하지 않고 현재 결과로 응답 생성"
        )

    parser = PydanticOutputParser(pydantic_object=EvaluationOutput)

    prompt = ChatPromptTemplate.from_template(
        "당신은 도구 실행 결과를 평가하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
        "사용자 질문: {query}\n"
        "원래 계획: {plan}\n"
        "도구 실행 결과: {tool_results}\n"
        "현재 재시도 횟수: {retry_count}\n\n"
        "도구 실행 결과를 평가하고 다음 단계를 결정하세요:\n\n"
        "1. **success**: 도구 실행 결과가 충분하고 사용자 질문에 답변 가능\n"
        "2. **retry**: 도구 실행 실패 또는 결과 불충분 (같은 도구 재실행)\n"
        "3. **replanning**: 계획 자체가 잘못됨 (다른 접근 방법 필요)\n\n"
        "평가 기준:\n"
        "- 계획과 실행 결과가 일치하는가?\n"
        "- 결과가 질문에 답하기에 충분한가?\n"
        "- 추가 정보나 다른 도구가 필요한가?\n\n"
        "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
        "{format_instructions}\n\n"
        "예시:\n"
        '{{"evaluation": "결과가 충분함", "status": "success", "reason": "질문에 답변 가능"}}'
    )

    chain = prompt | get_evaluator_llm() | parser

    try:
        result = None
        async for chunk in chain.astream({
            "query": query,
            "plan": plan,
            "tool_results": tool_results or "도구 실행 결과 없음",
            "retry_count": retry_count,
            "format_instructions": parser.get_format_instructions()
        }):
            result = chunk  # parser는 최종 결과만 반환

        if result is None:
            raise ValueError("LLM 스트림에서 결과를 받지 못함")

        logger.info(f"평가: {result.evaluation}")
        logger.info(f"Status: {result.status}")

        # status 유효성 검증
        valid_statuses = ["success", "retry", "replanning"]
        if result.status not in valid_statuses:
            logger.warning(f"잘못된 status: {result.status}, 'success'로 변경")
            result.status = "success"

        # retry인 경우 카운트 증가
        new_retry_count = retry_count + 1 if result.status == "retry" else retry_count

        return OrchestrationState(
            evaluation=result.evaluation,
            evaluation_status=result.status,
            evaluation_reason=result.reason,
            retry_count=new_retry_count
        )

    except Exception as e:
        logger.error(f"Evaluator 단계에서 에러 발생: {e}")
        # 에러 발생 시 안전하게 success 처리
        return OrchestrationState(
            evaluation="평가 실패",
            evaluation_status="success",
            evaluation_reason="평가 중 오류 발생, 현재 결과로 응답 생성",
            retry_count=retry_count
        )
