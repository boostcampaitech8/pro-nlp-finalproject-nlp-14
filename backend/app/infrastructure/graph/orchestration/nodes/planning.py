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
    next_subquery: str | None = Field(
        default=None,
        description="재계획 시 다음 단계에서 사용할 구체적 서브-쿼리 (없으면 null)",
    )
    required_topics: list[str] = Field(
        default_factory=list,
        description="추가 컨텍스트가 필요한 L1 토픽 이름 목록 (없으면 빈 리스트)",
    )

# Planning node
async def create_plan(state: OrchestrationState) -> OrchestrationState:
    """계획 수립 노드

    Contract:
        reads: messages, retry_count, evaluation, evaluation_reason
        writes: plan, need_tools
        side-effects: LLM API 호출
        failures: PLANNING_FAILED -> 기본 계획 반환

    Fast-Track 라우팅:
    - 단순 쿼리는 Planner LLM 호출 없이 직접 MIT Tools로
    - 쿼리 길이 < 25 또는 팩트 키워드 포함 → 직행
    """
    logger.info("Planning 단계 진입")

    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""

    # Fast-Track 라우팅 (Planner LLM 호출 없이)
    if query:
        is_simple_query = len(query) < 25
        fact_keywords = ["누구", "뭐", "언제", "어디", "전화", "이메일", "주소", "이름"]
        has_fact_keyword = any(kw in query for kw in fact_keywords)

        if is_simple_query or has_fact_keyword:
            logger.info(f"[Fast-Track] 단순 쿼리 감지: {query[:50]}")
            # Fast-Track: 직접 MIT Tools로 이동
            return {
                "plan": f"직접 검색: {query}",
                "need_tools": True,
                "fast_track": True,  # 플래그 추가
                "required_topics": [],
            }

    # 이미 계획이 준비된 경우 스킵 (테스트/외부 오케스트레이션 용도)
    if state.get("skip_planning") and state.get("plan"):
        logger.info("Planning 단계 스킵: 기존 plan 사용")
        return {
            "plan": state.get("plan", ""),
            "need_tools": state.get("need_tools", False),
            "required_topics": state.get("required_topics", []),
        }

    retry_count = state.get('retry_count', 0)
    planning_context = state.get("planning_context", "")

    # 재계획인 경우 이전 평가 결과 참고
    previous_evaluation = state.get('evaluation', '')
    evaluation_reason = state.get('evaluation_reason', '')

    parser = PydanticOutputParser(pydantic_object=PlanningOutput)

    if retry_count > 0:
        # 재계획: 복합 쿼리 처리 (다단계 검색)
        template_text = (
            "당신은 다단계 검색을 계획하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "원래 질문: {query}\n"
            "컨텍스트 요약 (L0/L1 토픽 목록):\n{planning_context}\n\n"
            "이전 검색 결과 평가:\n"
            "  - 평가: {previous_evaluation}\n"
            "  - 이유: {evaluation_reason}\n\n"
            "지시사항 - 복합 쿼리 처리:\n"
            "1. 사용자의 원래 질문을 다시 읽으세요\n"
            "2. 이전 검색에서 부족한 부분을 명확히 파악하세요\n"
            "3. 다음 검색에서 찾아야 할 것을 구체적으로 명시하세요\n\n"
            "예시:\n"
            "Q: '교육 프로그램 상반기 내 완료 목표를 맡고 있는 사람과 같은 팀원인 사람이 누구야?'\n"
            "첫 검색: 액션 아이템 [교육 프로그램 상반기 내 완료 목표]\n"
            "부족한 것: 담당자와 그 담당자의 팀원\n"
            "다음 계획: MIT Search로 담당자 찾고, 그 담당자의 팀원 찾기\n\n"
            "중요:\n"
            "- need_tools: true (계속 검색 필요)\n"
            "- plan: \"1단계: ... → 2단계: ...\" 형식\n"
            "- next_subquery: 다음 검색 단계에서 사용할 구체적인 한국어 질의\n"
            "  예: \"이전에 찾은 교육 프로그램 상반기 내 완료 목표의 담당자는 누구야?\"\n"
            "- JSON만 출력\n\n"
            "{format_instructions}"
        )
        prompt = ChatPromptTemplate.from_template(template_text)
    else:
        # 초기 계획
        template_text = (
            "당신은 계획을 세우는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "사용자 질문: {query}\n\n"
            "컨텍스트 요약 (L0/L1 토픽 목록):\n{planning_context}\n\n"
            "이 질문에 대한 답변을 하기 위한 계획을 세우세요.\n"
            "외부 정보(검색, 요약 등)가 필요하면 need_tools를 true로 설정하세요.\n"
            "간단한 인사나 일반 상식으로 답변 가능하면 need_tools를 false로 설정하세요.\n\n"
            "추가 컨텍스트가 필요한 L1 토픽이 있으면 required_topics에 정확한 토픽명을 넣고,\n"
            "필요 없으면 빈 리스트로 두세요.\n\n"
            "재계획이 아닌 경우 next_subquery는 null로 설정하세요.\n\n"
            "중요: JSON만 출력하세요!\n\n"
            "{format_instructions}"
        )
        prompt = ChatPromptTemplate.from_template(template_text)

    chain = prompt | get_planner_llm() | parser

    try:
        # astream에 전달할 인자들 준비
        stream_args = {
            "query": query,
            "planning_context": planning_context or "없음",
            "format_instructions": parser.get_format_instructions()
        }

        # 재계획인 경우 평가 결과도 포함
        if retry_count > 0:
            stream_args["previous_evaluation"] = previous_evaluation
            stream_args["evaluation_reason"] = evaluation_reason

        result = None
        async for chunk in chain.astream(stream_args):
            result = chunk

        if result is None:
            raise ValueError("LLM 스트림에서 결과를 받지 못함")

        logger.info(f"생성된 Plan: {result.plan}")
        logger.info(f"도구 사용 필요 여부: {result.need_tools}")
        logger.info(f"판단 근거: {result.reasoning}")
        logger.info(f"추가 토픽 필요: {result.required_topics}")

        next_subquery = result.next_subquery if retry_count > 0 else None
        if retry_count > 0:
            logger.info(f"[Replanning] 원래 쿼리: {query}")
            logger.info(f"[Replanning] 다음 단계 쿼리: {next_subquery}")

        return {
            "plan": result.plan,
            "need_tools": result.need_tools,
            "next_subquery": next_subquery,
            "required_topics": result.required_topics,
        }

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")
        return OrchestrationState(
            plan="계획 수립 실패",
            need_tools=False,
            next_subquery=None,
            required_topics=[],
        )


