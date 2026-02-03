import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import get_planner_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState

logger = logging.getLogger(__name__)

class PlanningOutput(BaseModel):
    plan: str = Field(description="사용자의 질문을 해결하기 위한 단계별 계획")
    need_tools: bool = Field(description="검색이나 추가 정보가 필요하면 True, 아니면 False")
    can_answer: bool = Field(description="현재 워크플로우의 도구/로직으로 답변 가능하면 True")
    reasoning: str = Field(description="도구 필요 여부 판단 근거")
    next_subquery: str | None = Field(
        default=None,
        description="재계획 시 다음 단계에서 사용할 구체적 서브-쿼리 (없으면 null)",
    )
    missing_requirements: list[str] = Field(
        default_factory=list,
        description="답변에 필요한데 현재 없는 정보/도구 목록\n"
        "- 'weather_api': 실시간 날씨 정보 필요 → '죄송합니다. 날씨 정보는 현재 접근할 수 없습니다.'\n"
        "- 'stock_api': 실시간 금융 정보 필요 → '죄송합니다. 금융 정보는 현재 접근할 수 없습니다.'\n"
        "- 'web_search': 인터넷 검색 필요 → '죄송합니다. 그 정보는 현재 저는 알 수 없습니다.'\n"
        "- 'mit_action': 데이터 생성/수정 필요 → '그 작업은 현재 지원하지 않습니다.'\n"
        "- 'query_analysis_error': 질문 분석 오류 → '죄송합니다. 질문을 이해하는 데 어려움이 있습니다.'\n"
    )

# ===== missing_requirements 대응 메시지 매핑 =====
# 워크플로우의 마지막 단계(Response Generation)에서 사용:
TOOL_UNAVAILABLE_MESSAGES = {
    "weather_api": "죄송합니다. 날씨 정보는 실시간 데이터로 현재 저는 접근할 수 없습니다.",
    "stock_api": "죄송합니다. 금융 정보(주가, 환율 등)는 실시간 데이터로 현재 저는 접근할 수 없습니다.",
    "web_search": "죄송합니다. 인터넷 검색 정보는 현재 저는 접근할 수 없습니다.",
    "mit_action": "죄송합니다. 데이터 생성/수정은 현재 지원하지 않습니다.",
    "query_analysis_error": "죄송합니다. 질문을 이해하는 데 어려움이 있습니다.",
}

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

    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""

    # 이미 계획이 준비된 경우 스킵 (테스트/외부 오케스트레이션 용도)
    if state.get("skip_planning") and state.get("plan"):
        logger.info("Planning 단계 스킵: 기존 plan 사용")
        return {
            "plan": state.get("plan", ""),
            "need_tools": state.get("need_tools", False),
            "can_answer": state.get("can_answer", True),
            "missing_requirements": state.get("missing_requirements", []),
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
            "Role: Graph-based Task Management System Orchestrator - Replanning Mode\n"
            "당신은 사내 GT(Graph-based Task Management) 시스템의 작업 계획 담당자입니다.\n"
            "반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "=== mit_search가 하는 일 ===\n"
            "mit_search는 **회의에서 논의되고 회의록에 기록된 내용만** 검색합니다.\n\n"
            "✅ 검색 가능: 회의 내용, 회의 결정사항, 회의에서 할당된 작업, 팀 정보\n"
            "❌ 검색 불가: 개인 일정, 일반 지식, 외부 정보, 인터넷 정보\n\n"
            "핵심: \"이 정보가 회의록에 기록되어 있을까?\" → YES면 mit_search 사용\n\n"
            "=== 회의록에 없는 것들 (mit_search 불가) ===\n"
            "개인 일정, 일반 지식, 외부 정보, 데이터 생성 요청은 회의록에 없습니다.\n"
            "→ 해당하면 can_answer=false, need_tools=false, 적절한 missing_requirements 설정\n\n"
            "원래 질문: {query}\n"
            "GT 시스템 컨텍스트: {planning_context}\n\n"
            "이전 도구 실행 결과:\n"
            "  - 평가: {previous_evaluation}\n"
            "  - 이유: {evaluation_reason}\n\n"
            "=== REPLANNING TASK ===\n"
            "이전 실행 결과를 바탕으로:\n"
            "1. 질문이 mit_search 사용 조건을 만족하는가 재확인\n"
            "2. 추가 정보가 필요한 경우 → next_subquery에 구체적인 서브쿼리 작성\n"
            "3. 충분한 정보를 얻은 경우 → need_tools=false로 설정\n"
            "4. 답변 불가능 유형에 해당 → can_answer=false, need_tools=false, 해당 missing_requirements 설정\n\n"
            "=== OUTPUT FORMAT ===\n"
            "{format_instructions}"
        )
        prompt = ChatPromptTemplate.from_template(template_text)
    else:
        # 초기 계획
        template_text = (
            "Role: Graph-based Task Management System Orchestrator - Initial Planning Mode\n"
            "당신은 사내 GT(Graph-based Task Management) 시스템의 작업 계획 담당자입니다.\n"
            "반드시 JSON 형식으로만 응답해야 합니다.\n\n"
            "=== mit_search가 하는 일 ===\n"
            "mit_search는 **회의에서 논의되고 회의록에 기록된 내용만** 검색합니다.\n\n"
            "데이터 출처: 사내 회의록 (Meeting, Decision, ActionItem, User, Team 노드)\n"
            "검색 방식: Neo4j 그래프 데이터베이스에서 회의록 내용 검색\n\n"
            "✅ mit_search로 검색 가능한 것:\n"
            "1. 특정 회의의 내용 (예: \"AI팀 지난주 회의 내용\")\n"
            "2. 회의에서 내린 결정사항 (예: \"AI팀 결정사항\")\n"
            "3. 회의에서 할당된 액션 아이템 (예: \"회의에서 나한테 할당된 작업\")\n"
            "4. 팀 구조/담당자 정보 (예: \"AI팀 리더가 누구야\")\n"
            "5. 회의 참석자, 회의 날짜 등\n\n"
            "❌ mit_search로 검색 불가능한 것:\n"
            "1. 회의에 기록되지 않은 개인의 할 일\n"
            "   예: \"나 오늘 뭐해야해?\" → 이건 당신의 개인 일정이지 회의록이 아닙니다\n"
            "2. 일반 지식/상식\n"
            "   예: \"파이썬이 뭐야?\" → 회의록에 프로그래밍 언어 정의가 있나요?\n"
            "3. 외부 실시간 정보\n"
            "   예: \"오늘 날씨\", \"삼성전자 주가\" → 회의록에 없습니다\n"
            "4. 인터넷 일반 정보\n"
            "   예: \"뉴스\", \"튜토리얼\" → 회의록에 없습니다\n\n"
            "=== 핵심 판단 기준 ===\n"
            "질문을 받으면 다음을 생각하세요:\n\n"
            "1. \"이 정보가 회의에서 논의되었을까?\"\n"
            "   YES → 2번으로\n"
            "   NO → mit_search 불가\n\n"
            "2. \"이 정보가 회의록에 기록되어 있을까?\"\n"
            "   YES → mit_search 사용\n"
            "   NO → mit_search 불가\n\n"
            "예시:\n"
            "Q: \"나 오늘 뭐해야해?\"\n"
            "A: 당신의 개인 할 일이 회의에서 논의되었나요? → 아니요 → mit_search 불가\n\n"
            "Q: \"AI팀 회의에서 내게 할당된 작업\"\n"
            "A: 회의에서 할당된 작업이 회의록에 있나요? → 예 → mit_search 사용\n\n"
            "Q: \"회의에서 부산에서 회식하기로 결정했 부산까지 어떻게 가?\"\n"
            "A: 질문의 핵심은 '부산까지 어떻게 가?'입니다. 교통 정보가 회의록에? → 아니요 → mit_search 불가, web_search 필요\n\n"
            "=== 회의록에 없는 것들 (mit_search 불가) ===\n"
            "다음은 회의록에 기록되지 않으므로 mit_search로 찾을 수 없습니다:\n\n"
            "❌ 개인 일정 → missing_requirements=[\"query_analysis_error\"]\n"
            "   예: \"나 오늘 뭐해야해\", \"내 일정\"\n"
            "   이유: 당신의 개인 할 일은 회의록이 아닙니다\n\n"
            "❌ 일반 지식 → missing_requirements=[\"web_search\"]\n"
            "   예: \"파이썬이 뭐야\", \"시간이 몇 시야\"\n"
            "   이유: 회의록은 백과사전이 아닙니다\n\n"
            "❌ 외부 정보 → weather_api, stock_api, web_search\n"
            "   예: \"날씨\", \"주가\", \"뉴스\"\n"
            "   이유: 회의록은 외부 실시간 정보를 담지 않습니다\n\n"
            "❌ 데이터 생성 → missing_requirements=[\"mit_action\"]\n"
            "   예: \"회의 만들어줘\", \"할당해줘\"\n"
            "   이유: 검색이 아닌 생성 작업입니다\n\n"
            "❌ 무의미한 입력 → missing_requirements=[\"query_analysis_error\"]\n"
            "   예: \"꿍\", \"ㅋㅋㅋ\"\n\n"
            "사용자 질문: {query}\n\n"
            "GT 시스템 컨텍스트 (L0/L1 토픽):\n{planning_context}\n\n"
            "=== 판단 프로세스 ===\n"
            "다음 질문에 답하세요:\n\n"
            "1. 이 질문이 의미가 있나요?\n"
            "   - \"꿍\", \"ㅋㅋ\" 같은 무의미한 입력인가요?\n"
            "   → YES: missing_requirements=[\"query_analysis_error\"]\n\n"
            "2. 간단한 인사/감정 표현인가요?\n"
            "   - \"안녕\", \"고마워\" 같은 인사인가요?\n"
            "   → YES: can_answer=true, need_tools=false\n\n"
            "3. 이 정보가 회의록에 기록되어 있을까요?\n"
            "   생각해보세요:\n"
            "   - \"나 오늘 뭐해야해?\" → 당신의 개인 할 일이 회의록에? → NO\n"
            "   - \"파이썬이 뭐야?\" → 프로그래밍 언어 설명이 회의록에? → NO\n"
            "   - \"AI팀 회의 결정사항\" → 회의 결정사항이 회의록에? → YES\n"
            "   - \"담당자가 누구야?\" → 팀 담당자 정보가 회의록에? → YES\n\n"
            "   → YES: can_answer=true, need_tools=true, mit_search 사용\n"
            "   → NO: can_answer=false, need_tools=false, 적절한 missing_requirements 설정\n"
            "        (날씨→weather_api, 주가→stock_api, 일반지식→web_search, 개인일정→query_analysis_error)\n\n"
            "=== OUTPUT FORMAT ===\n"
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

        # ✅ 모순 검증 및 수정: missing_requirements가 있으면 need_tools는 False여야 함
        if result.missing_requirements and result.need_tools:
            logger.warning(
                f"Planning 모순 감지: need_tools=True + missing_requirements={result.missing_requirements}. "
                "need_tools를 False로 수정합니다."
            )
            result.need_tools = False

        # ✅ 감정 표현/인사 오분류 수정: fallback 키워드와 일치하면 can_answer=True로 수정
        query_lower = query.lower()
        greeting_keywords = ["안녕", "배고파", "졸려", "피곤", "기분", "느낌", "감정", "안녕하세요", "고마워", "감사"]
        if any(keyword in query_lower for keyword in greeting_keywords):
            if not result.can_answer or result.missing_requirements:
                logger.warning(
                    f"감정/인사 표현 오분류 감지: '{query}' → can_answer=True로 수정"
                )
                result.can_answer = True
                result.need_tools = False
                result.missing_requirements = []
                result.plan = "인사 또는 감정 표현"

        # ✅ missing_requirements가 있어도 can_answer=True로 설정 (자연스러운 거절 답변 생성)
        if result.missing_requirements and not result.can_answer:
            logger.warning(
                f"missing_requirements 감지: {result.missing_requirements} → can_answer=True로 수정 (자연스러운 거절 답변)"
            )
            result.can_answer = True

        logger.info(f"생성된 Plan: {result.plan}")
        logger.info(f"도구 사용 필요 여부: {result.need_tools}")
        logger.info(f"답변 가능 여부: {result.can_answer}")
        logger.info(f"판단 근거: {result.reasoning}")
        logger.info(f"부족한 요소: {result.missing_requirements}")

        next_subquery = result.next_subquery if retry_count > 0 else None
        if retry_count > 0:
            logger.info(f"[Replanning] 원래 쿼리: {query}")
            logger.info(f"[Replanning] 다음 단계 쿼리: {next_subquery}")

        return {
            "plan": result.plan,
            "need_tools": result.need_tools,
            "can_answer": result.can_answer,
            "next_subquery": next_subquery,
            "missing_requirements": result.missing_requirements,
        }

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")

        # 질문 분석을 통해 적절한 에러 응답 생성
        # 순서가 중요: 의미 없는 입력 → 회의록 키워드 → 기타 순서로 검사
        query_lower = query.lower()
        query_stripped = query.strip()

        # 0순위: 의미 없는 입력 감지
        # - 너무 짧거나 (2글자 이하, 단 의미 있는 키워드 제외)
        # - 반복 문자 (ㅋㅋㅋ, ..., ㅠㅠㅠ)
        # - 자음/모음만 있는 경우
        meaningful_short_words = ["회의", "팀", "누구", "언제", "어디", "뭐", "왜"]
        is_too_short = len(query_stripped) <= 2 and query_stripped not in meaningful_short_words
        is_repetitive = len(set(query_stripped)) <= 2 and len(query_stripped) > 2  # 같은 문자 반복
        is_only_consonants = all(ord('ㄱ') <= ord(c) <= ord('ㅎ') or c in [' ', '.', '!', '?'] for c in query_stripped)

        if is_too_short or is_repetitive or is_only_consonants:
            logger.warning(f"의미 없는 입력 감지: {query}")
            return {
                "plan": "의미 없는 입력",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["query_analysis_error"],
            }

        # 1순위: 사내 회의록 관련 질문 (회의, 결정사항, 액션, 팀, 담당자 등 명시적 키워드)
        if any(keyword in query_lower for keyword in ["회의", "결정사항", "액션", "팀", "회의록", "담당자", "아이템", "협의", "합의", "안건"]):
            logger.warning("LLM 에러로 인해 fallback 규칙으로 처리: mit_search 필요로 판단")
            return {
                "plan": "사내 회의록 검색을 통한 정보 수집",
                "need_tools": True,
                "can_answer": True,
                "next_subquery": query,
                "missing_requirements": [],
            }

        # 2순위: 간단한 인사/감정 표현 (회의록 검색 필요 없음)
        elif any(keyword in query_lower for keyword in ["안녕", "배고파", "졸려", "피곤", "기분", "느낌", "감정", "안녕하세요"]):
            return {
                "plan": "인사 또는 감정 표현",
                "need_tools": False,
                "can_answer": True,
                "next_subquery": None,
                "missing_requirements": [],
            }

        # 3순위: 날씨 관련 키워드
        elif any(keyword in query_lower for keyword in ["날씨", "기온", "강우", "미세먼지", "습도", "바람", "기상"]):
            return {
                "plan": "날씨 정보 요청",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["weather_api"],
            }

        # 4순위: 금융/주가 관련 키워드
        elif any(keyword in query_lower for keyword in ["주가", "주식", "환율", "금리", "지수", "수익률", "배당"]):
            return {
                "plan": "금융 정보 요청",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["stock_api"],
            }

        # 5순위: 인터넷 검색 관련 키워드
        elif any(keyword in query_lower for keyword in ["뉴스", "튜토리얼", "위키", "검색", "인터넷"]):
            return {
                "plan": "인터넷 정보 검색 요청",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["web_search"],
            }

        # 5-1순위: 개인 일정/할 일 질문 (회의록과 무관한 개인적 질문)
        # "나 오늘 뭐해야", "내 일정", "나 뭐하지" 등 개인적 스케줄 질문
        personal_schedule_patterns = [
            "나 오늘", "나 뭐", "내 일정", "내 스케줄", "나 뭐하",
            "나한테", "내가 오늘", "내가 뭐", "오늘 뭐해야",
            "내일 뭐해야", "이번주 뭐해야"
        ]
        # 회의록 맥락(액션 아이템, 회의 등)이 명시적으로 있으면 제외
        has_explicit_meeting_context = any(keyword in query_lower for keyword in ["회의", "액션", "아이템", "결정", "담당자", "할당"])
        if not has_explicit_meeting_context and any(pattern in query_lower for pattern in personal_schedule_patterns):
            logger.warning(f"개인 일정 질문 감지: {query}")
            return {
                "plan": "개인 일정/스케줄 질문",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["query_analysis_error"],
            }

        # 5-2순위: 일반 지식/상식 질문 (회의록과 무관)
        # "~이 뭐야", "~란", "어떻게", "방법" 등 일반 학습/정보 요청
        general_knowledge_patterns = [
            "이 뭐", "이란", "이 무엇", "가 뭐", "란 무엇",
            "어떻게", "방법", "어떻게 하", "설명",
            "시간이 몇", "몇 시", "오늘 날짜", "무슨 요일"
        ]
        # 단, 회의록 관련 키워드가 있으면 제외
        has_meeting_context = any(keyword in query_lower for keyword in ["회의", "결정", "액션", "팀", "담당"])
        if not has_meeting_context and any(pattern in query_lower for pattern in general_knowledge_patterns):
            logger.warning(f"일반 지식 질문 감지: {query}")
            return {
                "plan": "일반 지식/상식 질문",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["web_search"],
            }

        # 6순위: 데이터 생성/수정 관련 키워드
        elif any(keyword in query_lower for keyword in ["만들어줘", "등록해줘", "할당해줘", "추가해줘", "생성", "수정"]):
            return {
                "plan": "데이터 생성/수정 요청",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["mit_action"],
            }

        # 기본값: 판단 불가능한 질문
        else:
            return {
                "plan": "질문 분석 중 오류 발생",
                "need_tools": False,
                "can_answer": False,
                "next_subquery": None,
                "missing_requirements": ["query_analysis_error"],
            }
