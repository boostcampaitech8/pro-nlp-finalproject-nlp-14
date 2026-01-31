"""쿼리 의도 분석 노드 - LLM 기반 쿼리 분류 + 신뢰도 조정"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.graph.integration.llm import get_query_intent_analyzer_llm

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
        - entity_search: 특정 엔티티 검색
        - temporal_search: 시간 기반 검색
        - general_search: 일반 키워드 검색
        - meta_search: 메타데이터 검색
    """
    logger.info("Starting query intent analysis")

    try:
        query = state.get("mit_search_query", "")
        if not query:
            messages = state.get("messages", [])
            message = state.get("message", "")
            if messages:
                last_message = messages[-1]
                query = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )
            elif message:
                query = message

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

        return {
            "mit_search_query": query,
            "mit_search_query_intent": intent,
        }

    except Exception as e:
        logger.error(f"Query intent analysis failed: {e}")
        return {
            "mit_search_query_intent": {
                "intent_type": "general_search",
                "primary_entity": None,
                "search_focus": None,
                "date_range": None,
                "entity_types": None,
                "confidence": 0.1,
                "reasoning": "LLM intent analysis failed",
                "fallback_used": False,
            }
        }
async def _analyze_intent_with_llm(query: str) -> dict:
    """LLM으로 쿼리의 의도를 분석합니다."""
    llm = get_query_intent_analyzer_llm()

    system_prompt = """당신은 mit_search를 위한 쿼리 의도/필터 분석기입니다.
목표: 검색 대상과 조건을 명확히 추출하여 mit_search가 정확한 결과를 반환하도록 돕습니다.

사용자의 쿼리를 분석하여 다음 JSON을 반환하세요:

{
    "intent_type": "entity_search|temporal_search|general_search|meta_search",
    "primary_entity": "실제 사람이름 또는 팀명 (예: '신수효', '프로덕션팀') 또는 null",
    "search_focus": "Decision|Meeting|Agenda|Action|Team|Composite|null",
    "date_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} 또는 null,
    "entity_types": ["Decision", "Meeting", "Agenda", "Action", "Team"] 또는 null,
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
- Team: "팀", "팀원", "같은 팀"
- Composite: "담당자와 같은 팀원", "맡고 있는 사람과 팀원" (복합 검색 - 한 번에 처리)

**중요 1**: 메타 질문("누가", "누구", "담당자")이 있으면 meta_search로 분류합니다.
**중요 1-1**: mit_search는 읽기 전용 검색입니다. 실행/수정/외부 웹 요청은 검색 의도로 보지 마세요.

**중요 2 - 복합 쿼리**: "같은 팀원"이나 "팀원인 누구"는 두 단계 검색이 필요할 수 있습니다:
- 단순 팀원 검색: "신수효랑 같은 팀인 사람은?" → entity_search + Team (단일 Cypher)
- 복합 검색: "교육 프로그램 담당자와 같은 팀원은?" → meta_search + Composite (multi-hop Cypher로 한 번에 처리)

**판별 기준**:
- 명확한 사람 이름 + "같은 팀"/"팀원" → entity_search + Team
- "맡고 있는/담당하는" + "같은 팀"/"팀원" → meta_search + Composite

**중요 3**: "상반기", "1월" 등의 시간 정보가 있으면 temporal_search로 분류하되, search_focus는 시간이 가리키는 대상으로 설정합니다.

**중요 4 - 한국 이름 명확 인식**:
- "신수효", "김철수", "박영희" 같은 2-3글자 한국 이름은 반드시 개인명(primary_entity)으로 추출
- "신수"가 나와도 뒤에 글자가 더 있으면 한국 이름 우선 (신수효 ≠ 신수(신화의 동물))
- 이름 뒤에 "가", "이", "가 맡은", "이 담당" 등이 있으면 더욱 확실한 사람 이름
- "신수효 관련", "신수효가 맡은", "신수효 담당" → 무조건 primary_entity: "신수효"

**필터 추출 규칙**:
- date_range: "지난주" → {"start": "2026-01-24", "end": "2026-01-31"}, "이번달" → {"start": "2026-01-01", "end": "2026-01-31"}
  * 시간 표현이 없으면 null
  * YYYY-MM-DD 형식으로 반환
- entity_types: search_focus에 해당하는 엔티티 타입 리스트
  * "결정사항" → ["Decision"]
  * "회의" → ["Meeting"]
  * search_focus가 null이면 entity_types도 null

**출력 규칙**:
- 검색 대상(search_focus)과 제약(primary_entity/date_range)을 최대한 명확히 지정
- 확신이 낮으면 confidence를 낮게 설정
- 출력은 JSON만 반환

예1: "신수효랑 같은 팀인 사람은 누구야?"
→ intent_type: "entity_search", primary_entity: "신수효", search_focus: "Team", date_range: null, entity_types: ["Team"], confidence: 0.95

예2: "지난주 결정사항"
→ intent_type: "temporal_search", primary_entity: null, search_focus: "Decision", date_range: {"start": "2026-01-24", "end": "2026-01-31"}, entity_types: ["Decision"], confidence: 0.9

예3: "교육 프로그램 상반기 내 완료 목표를 맡고 있는 사람과 같은 팀원인 사람이 누구야?"
→ intent_type: "meta_search", search_focus: "Composite", date_range: {"start": "2026-01-01", "end": "2026-06-30"}, entity_types: null, confidence: 0.7

예4: "신수효가 맡은 일 뭐가 있어?"
→ intent_type: "entity_search", primary_entity: "신수효", search_focus: "Action", date_range: null, entity_types: ["Action"], confidence: 0.95

예5: "신수효 팀원 누구 있어?"
→ intent_type: "entity_search", primary_entity: "신수효", search_focus: "Team", date_range: null, entity_types: ["Team"], confidence: 0.95

출력은 JSON만 반환하세요."""

    user_message = f"쿼리: {query}"

    response = await llm.ainvoke(
        [
            SystemMessage(system_prompt),
            HumanMessage(user_message),
        ]
    )

    content = response.content.strip()
    try:
        # 코드펜스 제거
        if content.startswith("```"):
            content = content.strip("`").replace("json", "", 1).strip()

        # JSON 추출
        import re
        if not content.startswith("{"):
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if match:
                content = match.group(0)

        parsed = json.loads(content)

        # entity_types 검증: search_focus와 일치하도록
        if parsed.get("search_focus") and not parsed.get("entity_types"):
            parsed["entity_types"] = [parsed["search_focus"]]

        return parsed
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM response: {content}")
        return {
            "intent_type": "general_search",
            "primary_entity": None,
            "search_focus": None,
            "date_range": None,
            "entity_types": None,
            "confidence": 0.1,
            "reasoning": "LLM response not JSON",
        }


def query_intent_analyzer(state: MitSearchState) -> dict:
    """동기 환경(테스트)용 래퍼"""
    import asyncio
    return asyncio.run(query_intent_analyzer_async(state))
