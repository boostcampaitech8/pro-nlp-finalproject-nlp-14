"""쿼리 의도 분석 노드 - LLM 기반 쿼리 분류 + 신뢰도 조정"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.graph.integration.llm import get_generator_llm

from ..state import MitSearchState
from ..utils.confidence_calibrator import CalibratedIntentValidator
from ..utils.query_validator import IntentAnalysisResult, QueryValidator

logger = logging.getLogger(__name__)

# 글로벌 검증자 (한 번만 초기화)
_validator: QueryValidator = None
_confidence_calibrator: CalibratedIntentValidator = None


def _get_validator() -> QueryValidator:
    """QueryValidator 싱글톤"""
    global _validator
    if _validator is None:
        _validator = QueryValidator()
    return _validator


def _get_confidence_calibrator() -> CalibratedIntentValidator:
    """CalibratedIntentValidator 싱글톤"""
    global _confidence_calibrator
    if _confidence_calibrator is None:
        _confidence_calibrator = CalibratedIntentValidator()
    return _confidence_calibrator


async def query_intent_analyzer_async(state: MitSearchState) -> dict:
    """LLM을 사용하여 쿼리의 의도를 분석합니다.

    Contract:
        reads: mit_search_query
        writes: mit_search_query_intent (intent_type, primary_entity, search_focus)
        side-effects: LLM API 호출 + Intent 검증
        failures: LLM 오류 → 기본값 반환

    의도 분류:
        - entity_search: 특정 엔티티 검색 ("신수효 관련 결정사항")
        - temporal_search: 시간 기반 검색 ("지난주 회의")
        - general_search: 일반 키워드 검색 ("팀 있어")
        - meta_search: 메타데이터 검색 ("누가, 누구, 담당자")
    """
    logger.info("Starting query intent analysis")

    try:
        query = state.get("mit_search_query", "")
        if not query:
            return {
                "mit_search_query_intent": {
                    "intent_type": "general_search",
                    "primary_entity": None,
                    "search_focus": None,
                    "confidence": 1.0,
                }
            }

        # LLM 분석
        intent = await _analyze_intent_with_llm(query)

        # 검증
        validator = _get_validator()
        result = IntentAnalysisResult(
            intent_type=intent.get("intent_type"),
            primary_entity=intent.get("primary_entity"),
            search_focus=intent.get("search_focus"),
            confidence=intent.get("confidence", 0.5),
            fallback_used=False,
            rule_conflict=False,
        )
        validation_report = validator.validate_intent(result, query)

        # ✅ P1: 신뢰도 조정 (검증 결과 기반)
        calibrator = _get_confidence_calibrator()
        calibration_result = calibrator.recalibrate_confidence(
            original_confidence=result.confidence,
            validation_results={
                "entity_exists": validator._validate_entity(
                    result.primary_entity, result.search_focus
                ) if result.primary_entity else True,
                "intent_pattern_matched": validation_report["is_valid"],
                "fallback_used": False,
                "result_count": 0,  # 실행 전이므로 0
            }
        )

        # 조정된 신뢰도를 intent에 반영
        intent["confidence"] = calibration_result["recalibrated_confidence"]
        intent["confidence_level"] = calibration_result["final_level"]
        intent["confidence_adjustment"] = round(
            calibration_result["total_adjustment"], 2
        )

        # 검증 결과 로깅
        if not validation_report["is_valid"]:
            logger.warning(
                f"Intent validation failed: {validation_report['issues']}",
                extra={
                    "query": query,
                    "intent": result.to_dict(),
                    "recommendations": validation_report["recommendations"],
                    "confidence_adjustment": calibration_result["total_adjustment"],
                },
            )

        logger.info(f"Query intent: {intent}")
        print(f"\n[의도분석] 쿼리: '{query}'")
        print(f"[의도분석] 분석결과: {intent}")
        print(
            f"[신뢰도] 원래: {result.confidence:.2f} → "
            f"조정됨: {calibration_result['recalibrated_confidence']:.2f} "
            f"({calibration_result['final_level']})"
        )
        print(f"[의도분석] 검증: {'✓ 통과' if validation_report['is_valid'] else '⚠ 경고'}")

        return {"mit_search_query_intent": intent}

    except Exception as e:
        logger.error(f"Query intent analysis failed: {e}")
        query = state.get("mit_search_query", "")
        result = _analyze_intent_with_rules(query)
        # Fallback 사용 표시
        result["fallback_used"] = True
        return {"mit_search_query_intent": result}


async def _analyze_intent_with_llm(query: str) -> dict:
    """LLM으로 쿼리의 의도를 분석합니다."""
    llm = get_generator_llm()

    system_prompt = """당신은 검색 쿼리의 의도를 분석하는 AI입니다.
사용자의 쿼리를 분석하여 다음 JSON을 반환하세요:

{
    "intent_type": "entity_search|temporal_search|general_search|meta_search",
    "primary_entity": "실제 사람이름 또는 팀명 (예: '신수효', '프로덕션팀') 또는 null",
    "search_focus": "Decision|Meeting|Agenda|Action|Team|null",
    "confidence": 0.0~1.0,
    "reasoning": "분석 이유 간단히"
}

의도 분류:
- entity_search: 특정 개인/팀 관련 검색 (예: "신수효 관련 결정사항" → primary_entity: "신수효")
- temporal_search: 시간 기반 검색 (예: "지난주 회의" → primary_entity: null)
- general_search: 일반 키워드 검색 (예: "팀 있어" → primary_entity: null)
- meta_search: "누가", "누구", "담당자", "책임자" 등의 메타데이터 질문

search_focus 분류:
- Decision: "결정사항", "결정", "의결"
- Meeting: "회의", "미팅"
- Agenda: "아젠다", "안건"
- Action: "액션", "과제", "담당", "책임", "맡다" (담당자 검색용)
- Team: "팀", "팀원"
- Composite: "담당자와 같은 팀원", "맡고 있는 사람과 팀원" (복합 검색 - 한 번에 처리)

**중요 1**: 메타 질문("누가", "누구", "담당자")이 있으면 meta_search로 분류합니다.

**중요 2 - 복합 쿼리**: "같은 팀원"이나 "팀원인 누구"는 두 단계 검색이 필요할 수 있습니다:
- 단순 팀원 검색: "신수효랑 같은 팀인 사람은?" → entity_search + Team (단일 Cypher)
- 복합 검색: "교육 프로그램 담당자와 같은 팀원은?" → meta_search + Composite (multi-hop Cypher로 한 번에 처리)

**판별 기준**:
- 명확한 사람 이름 + "같은 팀" → entity_search + Team
- "맡고 있는/담당하는" + "같은 팀" → meta_search + Composite

**중요 3**: "상반기", "1월" 등의 시간 정보가 있으면 temporal_search로 분류하되, search_focus는 시간이 가리키는 대상으로 설정합니다.

예1: "신수효랑 같은 팀인 사람은 누구야?"
→ intent_type: "entity_search", primary_entity: "신수효", search_focus: "Team"

예2: "교육 프로그램 상반기 내 완료 목표를 맡고 있는 사람과 같은 팀원인 사람이 누구야?"
→ intent_type: "meta_search", search_focus: "Composite" (한 번에 multi-hop Cypher로 처리)

출력은 JSON만 반환하세요."""

    user_message = f"쿼리: {query}"

    try:
        print("[의도분석] LLM 호출 시작...")
        content = ""

        # ainvoke 대신 astream 사용 (더 안정적)
        async for chunk in llm.astream(
            [
                SystemMessage(system_prompt),
                HumanMessage(user_message),
            ]
        ):
            if hasattr(chunk, 'content') and chunk.content:
                content += chunk.content

        content = content.strip()

        # 디버깅: 원본 응답 출력
        print(f"\n[의도분석 LLM 원본 응답]")
        print(f"{'='*80}")
        print(content if content else "(빈 응답)")
        print(f"{'='*80}\n")

        if not content:
            logger.warning("[의도분석] LLM이 빈 응답을 반환 → 규칙 기반 분석 사용")
            return _analyze_intent_with_rules(query)

    except Exception as e:
        logger.error(f"[의도분석] LLM 호출 실패: {e}", exc_info=True)
        print(f"[오류] LLM 호출 실패: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return _analyze_intent_with_rules(query)

    try:
        # 코드 블록 제거
        import re
        original_content = content
        if content.startswith("```"):
            content = re.sub(r"```(?:json)?\n?", "", content)
            content = content.strip("`").strip()
            print(f"[파싱] 코드 블록 제거 후: {content[:200]}")

        # 설명 텍스트 제거 (마크다운 스타일)
        lines = content.split("\n")
        cleaned_lines = []
        json_started = False
        for line in lines:
            # JSON 시작 감지
            if line.strip().startswith("{"):
                json_started = True
            # JSON 내부에서 설명 시작 패턴 감지 시 중단
            if json_started and re.match(r"^\s*(\*\*|==|--|#\s*설명|설명:)", line.strip()):
                break
            cleaned_lines.append(line)
        content = "\n".join(cleaned_lines).strip()
        print(f"[파싱] 설명 제거 후: {content[:200]}")

        # JSON 추출
        if not content.startswith("{"):
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if match:
                content = match.group(0)
                print(f"[파싱] JSON 추출 후: {content[:200]}")

        result = json.loads(content)
        logger.debug(f"[의도분석] LLM 응답 파싱 성공: {result}")
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response (원본 길이: {len(original_content)})")
        print(f"[파싱 실패] 원본: {original_content[:500]}")
        print(f"[파싱 실패] 처리 후: {content[:500]}")
        print(f"[파싱 실패] 에러: {e}")
        logger.debug(f"JSON decode error: {e}")
        return _analyze_intent_with_rules(query)


def _analyze_intent_with_rules(query: str) -> dict:
    """규칙 기반 쿼리 의도 분석."""
    query_lower = query.lower()

    # 사람 이름 감지 (한글 2-3글자) - 기본 규칙
    has_person_name = False
    person_name = None
    words = query.split()

    # 알려진 이름 목록 (프로젝트 관련자들)
    known_names = {"신수효", "박준서", "윤성욱", "이수빈", "이준서", "정성욱", "김효진", "이혜인", "김준호", "정우진", "오서현"}

    # 쿼리 전체에서 알려진 이름 찾기 (첫 단어이든 어디든)
    for name in known_names:
        if name in query:
            has_person_name = True
            person_name = name
            break

    # 팀 이름 감지
    has_team_name = False
    team_name = None
    known_teams = {"프로덕션팀", "마케팅팀", "개발팀", "디자인팀", "데이터팀", "서비스팀"}
    for team in known_teams:
        if team in query:
            has_team_name = True
            team_name = team
            break

    # 찾지 못했으면 첫 단어 확인 (2-3글자 한글)
    if not has_person_name and words and 2 <= len(words[0]) <= 3:
        first = words[0]
        if all('\uac00' <= c <= '\ud7a3' for c in first):
            # 제외할 단어들
            excluded = {"교육", "안건", "회의", "프로", "프로그", "완료", "프로젝트", "작업", "내용", "계획"}
            if first not in excluded:
                has_person_name = True
                person_name = first

    # 시간 표현 감지
    has_temporal = any(
        t in query
        for t in ["지난주", "이번주", "금주", "지난달", "이번달", "금월", "오늘", "어제", "언제", "상반기", "하반기", "내"]
    )

    # 메타데이터 질문 감지 (누가, 누구, 담당자, 책임자 등)
    # 주의: "팀인 누구야?" 같은 경우는 meta_question이 아니라 entity_search로 처리해야 함
    has_meta_question = any(
        q in query for q in ["누가", "누구", "언제", "어디", "왜", "뭐", "뭔", "하는 사람"]
    )

    # 특별한 경우: 사람 이름 있고 "팀인 누구야?" → entity_search로 처리
    if has_person_name and "팀" in query and ("누가" in query or "누구" in query):
        has_meta_question = False  # 이 경우 meta_question이 아니라 entity_search

    # 검색 포커스 감지
    search_focus = None
    if "결정" in query or "decision" in query_lower:
        search_focus = "Decision"
    elif "회의" in query or "meeting" in query_lower:
        search_focus = "Meeting"
    elif "아젠다" in query or "안건" in query or "agenda" in query_lower:
        search_focus = "Agenda"
    elif "액션" in query or "action" in query_lower or "과제" in query or "담당" in query or "책임" in query or "맡" in query:
        search_focus = "Action"
    elif "팀" in query or "team" in query_lower:
        search_focus = "Team"

    # 복합 쿼리 감지: "맡고 있는/담당" + "팀원/같은 팀" 패턴
    is_composite_query = False
    if ("같은 팀원" in query or "같은 팀" in query) and ("담당" in query or "맡" in query):
        # "교육 프로그램 담당자와 같은 팀원" → 한 번에 처리
        is_composite_query = True
    elif has_person_name and ("같은 팀" in query or "팀원" in query):
        # "신수효랑 같은 팀"은 단순 팀원 검색
        is_composite_query = False

    # 의도 결정 (알려진 entity 우선, 그다음 복합 쿼리)
    if has_person_name:
        # 알려진 사람 이름이 있으면 entity_search
        intent_type = "entity_search"
        primary_entity = person_name
    elif has_team_name:
        # 알려진 팀 이름이 있으면 entity_search
        intent_type = "entity_search"
        primary_entity = team_name
    elif is_composite_query:
        # 복합 쿼리: 한 번에 multi-hop Cypher로 처리
        intent_type = "meta_search"
        primary_entity = None
        search_focus = "Composite"  # 새로운 focus: composite_search 전략 사용
    elif has_meta_question and has_temporal:
        intent_type = "meta_search"
        primary_entity = None
    elif has_temporal:
        intent_type = "temporal_search"
        primary_entity = None
    elif has_meta_question:
        intent_type = "meta_search"
        primary_entity = None
    else:
        # ← 중요: entity 없으면 일반 검색으로 분류
        intent_type = "general_search"
        primary_entity = None

    return {
        "intent_type": intent_type,
        "primary_entity": primary_entity,
        "search_focus": search_focus,
        "confidence": 0.7,
        "reasoning": f"규칙기반 분석: {intent_type}"
    }


def query_intent_analyzer(state: MitSearchState) -> dict:
    """동기 환경(테스트)용 래퍼"""
    import asyncio
    return asyncio.run(query_intent_analyzer_async(state))
