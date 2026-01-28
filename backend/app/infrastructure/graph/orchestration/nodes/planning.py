import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import get_planner_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)

class PlanningOutput(BaseModel):
    plan: str = Field(description="사용자의 질문을 해결하기 위한 단계별 계획")
    need_tools: bool = Field(description="검색이나 추가 정보가 필요하면 True, 아니면 False")
    reasoning: str = Field(description="도구 필요 여부 판단 근거")

# Planning node
async def create_plan(state: OrchestrationState) -> OrchestrationState:
    """계획 수립 노드

    Contract:
        reads: messages, retry_count, evaluation, evaluation_reason
        writes: plan, need_tools
        side-effects: LLM API 호출
        failures: PLANNING_FAILED -> 기본 계획 반환
    """
    logger.info("Planning 단계 진입")
    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    retry_count = state.get('retry_count', 0)

    # 재계획인 경우 이전 평가 결과 참고
    previous_evaluation = state.get('evaluation', '')
    evaluation_reason = state.get('evaluation_reason', '')

    parser = PydanticOutputParser(pydantic_object=PlanningOutput)

    if retry_count > 0:
        # 재계획
        prompt = ChatPromptTemplate.from_template(
            "당신은 계획을 수정하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "사용자 질문: {query}\n"
            "이전 평가: {previous_evaluation}\n"
            "평가 이유: {evaluation_reason}\n\n"
            "이전 평가를 참고하여 더 나은 계획을 세우세요.\n"
            "외부 정보(검색, 요약 등)가 필요하면 need_tools를 true로 설정하세요.\n\n"
            "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
            "{format_instructions}\n\n"
            "예시:\n"
            '{{"plan": "1단계: 검색, 2단계: 분석", "need_tools": true, "reasoning": "최신 정보 필요"}}'
        )
    else:
        # 초기 계획
        prompt = ChatPromptTemplate.from_template(
            "당신은 계획을 세우는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "사용자 질문: {query}\n\n"
            "이 질문에 대한 답변을 하기 위한 계획을 세우세요.\n"
            "외부 정보(검색, 요약 등)가 필요하면 need_tools를 true로 설정하세요.\n"
            "간단한 인사나 일반 상식으로 답변 가능하면 need_tools를 false로 설정하세요.\n\n"
            "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
            "{format_instructions}\n\n"
            "예시:\n"
            '{{"plan": "간단한 인사 응답", "need_tools": false, "reasoning": "추가 정보 불필요"}}'
        )

    chain = prompt | get_planner_llm() | parser

    try:
        result = None
        async for chunk in chain.astream({
            "query": query,
            "previous_evaluation": previous_evaluation,
            "evaluation_reason": evaluation_reason,
            "format_instructions": parser.get_format_instructions()
        }):
            result = chunk  # parser는 최종 결과만 반환

        if result is None:
            raise ValueError("LLM 스트림에서 결과를 받지 못함")

        logger.info(f"Plan: {result.plan}")
        logger.info(f"도구 필요: {result.need_tools}")

        return OrchestrationState(
            plan=result.plan,
            need_tools=result.need_tools
        )

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")
        return OrchestrationState(
            plan="계획 수립 실패",
            need_tools=False
        )

