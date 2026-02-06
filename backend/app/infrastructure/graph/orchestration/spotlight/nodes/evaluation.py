import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.config import MAX_RETRY
from app.infrastructure.graph.integration.llm import get_evaluator_llm
from ..state import SpotlightOrchestrationState
from app.prompt.v1.orchestration.evaluation_node import EVALUATION_NODE_PROMPT

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)

class EvaluationOutput(BaseModel):
    """도구 실행 결과 평가 출력 모델.

    Attributes:
        evaluation: 평가 요약 (한 줄 설명)
        status: 평가 상태 (success, retry, replanning 중 하나)
        reason: 평가 이유 및 상세 설명
    """
    evaluation: str = Field(description="평가 요약 (예: '검색 결과 충분', '계획 재수립 필요')")
    status: str = Field(description="평가 상태: 'success', 'retry', 'replanning' 중 하나")
    reason: str = Field(description="평가 이유 및 상세 설명")


def _detect_composite_query(query: str, tool_results: str) -> bool:
    """복합 쿼리(여러 단계의 검색이 필요한 쿼리) 감지
    
    복합 쿼리 예시:
    - "교육 프로그램 담당자와 같은 팀원은 누구?" (O - 담당자를 먼저 찾아야 함)
    - "신수효랑 같은 팀원인 사람은 누구?" (X - 단순 팀원 검색)
    
    판별 기준: "맡고 있는/담당하는" + "팀원/같은 팀" 조합
    """
    query_lower = query.lower()
    
    # 복합 쿼리 필수 키워드: 담당자/책임자를 먼저 찾아야 하는 표현
    assignment_keywords = ["맡고 있는", "담당", "책임자", "담당자", "맡은"]
    
    # 추가 검색 키워드: 그 다음 팀/팀원을 찾는 표현
    team_keywords = ["팀원", "같은 팀", "팀에서", "팀의"]
    
    has_assignment = any(kw in query for kw in assignment_keywords)
    has_team = any(kw in query for kw in team_keywords)
    
    # 복합 쿼리: 담당자 검색 + 팀 검색 조합
    if has_assignment and has_team:
        logger.info(f"[복합감지] 담당({has_assignment}) + 팀({has_team})")
        return True
    
    return False



def _is_subquery(query: str) -> bool:
    """이 쿼리가 Replanning에서 생성된 서브-쿼리인지 확인
    
    서브-쿼리 특징:
    - "이전에 찾은", "그 담당자", "그 사람" 같은 컨텍스트 참조
    """
    subquery_keywords = [
        "이전에 찾은", "그 담당자", "그 사람", "그 액션",
        "그 팀원", "그 팀", "그 결정", "찾은"
    ]
    return any(kw in query for kw in subquery_keywords)


async def evaluate_result(state: SpotlightOrchestrationState) -> SpotlightOrchestrationState:

    messages = state.get('messages', [])
    query = messages[-1].content if messages else ""
    plan = state.get('plan', '')
    tool_results = state.get('tool_results', '')
    retry_count = state.get('retry_count', 0)
    hitl_status = state.get('hitl_status', 'none')

    logger.info(f"Evaluator 단계: retry_count={retry_count}, tool_results={bool(tool_results)}, hitl_status={hitl_status}")

    # 무한 루프 방지: MAX_RETRY 이상 재시도 시 강제로 success 처리
    if retry_count >= MAX_RETRY:
        logger.warning(f"최대 재시도 횟수({MAX_RETRY}) 도달 - 강제 완료 처리")
        return SpotlightOrchestrationState(
            evaluation="최대 재시도 횟수 도달",
            evaluation_status="success",
            evaluation_reason="더 이상 재시도하지 않고 현재 결과로 응답 생성"
        )

    # Mutation 도구 실행 완료 시 바로 success 처리 (HITL 중복 방지)
    mutation_success_markers = [
        "생성되었습니다", "수정되었습니다", "삭제되었습니다",
        '"success": true', "'success': True"
    ]
    if tool_results and any(marker in tool_results for marker in mutation_success_markers):
        logger.info("✓ Mutation 도구 실행 완료 → success")
        return SpotlightOrchestrationState(
            evaluation="Mutation 도구 실행 완료",
            evaluation_status="success",
            evaluation_reason="Mutation 작업이 성공적으로 완료됨"
        )

    # MIT Search 결과가 있으면 일반적으로 success 처리
    if tool_results and "[MIT Search 결과" in tool_results:
        logger.info("✓ MIT Search 결과 수신 → success")
        return SpotlightOrchestrationState(
            evaluation="검색 결과 충분",
            evaluation_status="success",
            evaluation_reason="MIT Search에서 결과 획득 (composite_search 전략 사용 시 한 번에 처리 완료)"
        )

    parser = PydanticOutputParser(pydantic_object=EvaluationOutput)

    prompt = ChatPromptTemplate.from_template(EVALUATION_NODE_PROMPT)

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

        # retry 또는 replanning인 경우 카운트 증가 (무한 루프 방지)
        new_retry_count = retry_count + 1 if result.status in ["retry", "replanning"] else retry_count

        return SpotlightOrchestrationState(
            evaluation=result.evaluation,
            evaluation_status=result.status,
            evaluation_reason=result.reason,
            retry_count=new_retry_count
        )

    except Exception as e:
        logger.error(f"Evaluator 단계에서 에러 발생: {e}")
        # 에러 발생 시 안전하게 success 처리
        return SpotlightOrchestrationState(
            evaluation="평가 실패",
            evaluation_status="success",
            evaluation_reason="평가 중 오류 발생, 현재 결과로 응답 생성",
            retry_count=retry_count
        )


def _suggest_next_steps(query: str, tool_results: str) -> str:
    """복합 쿼리의 다음 단계 제시"""
    if "팀원" in query or "같은 팀" in query:
        return "다음: 담당자 조회 후 같은 팀 멤버 찾기"
    elif "담당자" in query or "책임자" in query:
        return "다음: 담당자 정보 조회"
    elif "참석자" in query:
        return "다음: 회의 참석자 조회"
    else:
        return "다음: 추가 정보 검색"


def _extract_next_step_query_eval(query: str) -> str:
    """Turn 1 결과를 바탕으로 Turn 2 서브-쿼리 생성"""
    if "팀원" in query:
        return "이전에 찾은 담당자와 같은 팀의 팀원은 누구인가?"
    elif "같은 팀" in query or "팀에서" in query or "팀의" in query:
        return "이전에 찾은 담당자와 같은 팀의 팀원들은 누구인가?"
    else:
        return "이전에 찾은 담당자의 팀 정보는?"

