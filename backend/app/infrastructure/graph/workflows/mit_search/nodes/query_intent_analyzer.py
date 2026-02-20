"""쿼리 의도 분석 노드 - LLM 기반 쿼리 분류 + 신뢰도 조정"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.graph.integration.llm import get_query_intent_analyzer_llm
from app.prompt.v1.mit_search.query_intent import (
    QUERY_INTENT_SYSTEM_PROMPT,
    QUERY_INTENT_USER_PROMPT,
)

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
        reads: mit_search_query, messages, message
        writes: mit_search_query, mit_search_query_intent
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

    system_prompt = QUERY_INTENT_SYSTEM_PROMPT
    user_message = QUERY_INTENT_USER_PROMPT.format(query=query)

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
