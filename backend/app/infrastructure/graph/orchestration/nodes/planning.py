import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)

class PlanningOutput(BaseModel):
    plan: str = Field(description="사용자의 질문을 해결하기 위한 단계별 계획")
    need_tools: bool = Field(description="검색이나 추가 정보가 필요하면 True, 아니면 False")
    reasoning: str = Field(description="도구 필요 여부 판단 근거")
    required_topics: list[str] = Field(
        default_factory=list,
        description="추가 컨텍스트가 필요한 L1 토픽 이름 목록 (없으면 빈 리스트)",
    )

# Planning node
def create_plan(state: OrchestrationState):
    """계획 수립 노드
    
    Contract:
        reads: messages, retry_count, evaluation, evaluation_reason
        writes: plan, need_tools
        side-effects: LLM API 호출
        failures: PLANNING_FAILED -> errors 기록
    """
    logger.info("Planning 단계 진입")
    # 이미 계획이 준비된 경우 스킵 (테스트/외부 오케스트레이션 용도)
    if state.get("skip_planning") and state.get("plan"):
        logger.info("Planning 단계 스킵: 기존 plan 사용")
        return {
            "plan": state.get("plan", ""),
            "need_tools": state.get("need_tools", False),
            "required_topics": state.get("required_topics", []),
        }

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    retry_count = state.get('retry_count', 0)
    planning_context = state.get("planning_context", "")

    # 재계획인 경우 이전 평가 결과 참고
    previous_evaluation = state.get('evaluation', '')
    evaluation_reason = state.get('evaluation_reason', '')

    parser = PydanticOutputParser(pydantic_object=PlanningOutput)

    if retry_count > 0:
        # 재계획
        prompt = ChatPromptTemplate.from_template(
            "당신은 계획을 수정하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "사용자 질문: {query}\n"
            "컨텍스트 요약 (L0/L1 토픽 목록):\n{planning_context}\n\n"
            "이전 평가: {previous_evaluation}\n"
            "평가 이유: {evaluation_reason}\n\n"
            "이전 평가를 참고하여 더 나은 계획을 세우세요.\n"
            "외부 정보(검색, 요약 등)가 필요하면 need_tools를 true로 설정하세요.\n\n"
            "추가 컨텍스트가 필요한 L1 토픽이 있으면 required_topics에 정확한 토픽명을 넣고,\n"
            "필요 없으면 빈 리스트로 두세요.\n\n"
            "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
            "{format_instructions}\n\n"
            "예시:\n"
            '{{"plan": "1단계: 검색, 2단계: 분석", "need_tools": true, "reasoning": "최신 정보 필요", "required_topics": ["Topic_1"]}}'
        )
    else:
        # 초기 계획
        prompt = ChatPromptTemplate.from_template(
            "당신은 계획을 세우는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "사용자 질문: {query}\n\n"
            "컨텍스트 요약 (L0/L1 토픽 목록):\n{planning_context}\n\n"
            "이 질문에 대한 답변을 하기 위한 계획을 세우세요.\n"
            "외부 정보(검색, 요약 등)가 필요하면 need_tools를 true로 설정하세요.\n"
            "간단한 인사나 일반 상식으로 답변 가능하면 need_tools를 false로 설정하세요.\n\n"
            "추가 컨텍스트가 필요한 L1 토픽이 있으면 required_topics에 정확한 토픽명을 넣고,\n"
            "필요 없으면 빈 리스트로 두세요.\n\n"
            "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
            "{format_instructions}\n\n"
            "예시:\n"
            '{{"plan": "간단한 인사 응답", "need_tools": false, "reasoning": "추가 정보 불필요", "required_topics": []}}'
        )

    chain = prompt | llm | parser

    try:
        result = chain.invoke({
            "query": query,
            "previous_evaluation": previous_evaluation,
            "evaluation_reason": evaluation_reason,
            "planning_context": planning_context or "없음",
            "format_instructions": parser.get_format_instructions()
        })

        logger.info(f"생성된 Plan: {result.plan}")
        logger.info(f"도구 사용 필요 여부: {result.need_tools}")
        logger.info(f"판단 근거: {result.reasoning}")
        logger.info(f"추가 토픽 필요: {result.required_topics}")

        return {
            "plan": result.plan,
            "need_tools": result.need_tools,
            "required_topics": result.required_topics,
        }

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")
        return {
            "plan": "계획 수립 실패",
            "need_tools": False,
            "required_topics": [],
        }
