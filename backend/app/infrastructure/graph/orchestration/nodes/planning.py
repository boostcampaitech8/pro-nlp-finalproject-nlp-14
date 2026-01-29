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

        # 재계획인 경우: 계획에서 명시된 "다음 단계"를 새로운 쿼리로 변환
        # 예: "1단계: 담당자 찾기" → "이전에 찾은 액션의 담당자는 누구?"
        if retry_count > 0:
            next_step_query = _extract_next_step_query(result.plan, query)
            logger.info(f"[Replanning] 원래 쿼리: {query}")
            logger.info(f"[Replanning] 다음 단계 쿼리: {next_step_query}")
            
            # 새로운 쿼리를 messages에 추가
            from langchain_core.messages import HumanMessage
            messages = state.get('messages', [])
            if next_step_query != query:
                messages.append(HumanMessage(content=next_step_query))
                logger.info(f"[Replanning] 새로운 서브-쿼리 추가됨: {next_step_query}")

        return {
            "plan": result.plan,
            "need_tools": result.need_tools,
            "required_topics": result.required_topics,
        }

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")
        return OrchestrationState(
            plan="계획 수립 실패",
            need_tools=False,
            required_topics=[],
        )


def _extract_next_step_query(plan: str, original_query: str) -> str:
    """계획에서 다음 단계를 추출하여 새로운 서브-쿼리 생성
    
    예:
    - plan: "1단계: 교육프로그램 상반기 내 완료 목표의 담당자 찾기 → 2단계: 그 담당자와 팀원 찾기"
    - original_query: "교육프로그램 상반기 내 완료 목표를 맡고 있는 사람과 같은 팀원인 사람이 누구야?"
    - return: "이전에 찾은 교육프로그램 상반기 내 완료 목표의 담당자는 누구야?"
    """
    # 담당자 찾기 계획
    if "담당자" in plan and ("찾" in plan or "찾기" in plan):
        return "이전에 찾은 액션 아이템의 담당자는 누구야?"
    
    # 팀원 찾기 계획
    if "팀원" in plan and ("찾" in plan or "찾기" in plan):
        return "그 담당자와 같은 팀의 팀원은 누구야?"
    
    # 기본: 원래 쿼리 반환
    return original_query

