"""Calibrated Intent Validator - LLM 신뢰도 조정 (P1-2)"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CalibratedIntentValidator:
    """LLM 신뢰도를 실제 검증 결과로 조정"""

    # 신뢰도 조정 팩터
    CONFIDENCE_ADJUSTMENTS = {
        "entity_match": 0.3,  # 엔티티 존재 확인 시 +0.3
        "entity_mismatch": -0.4,  # 엔티티 없을 시 -0.4
        "pattern_match": 0.2,  # Intent 패턴 매칭 시 +0.2
        "fallback_used": -0.3,  # Fallback 전략 사용 시 -0.3
        "zero_results": -0.5,  # 결과 0개 시 -0.5
    }

    # 신뢰도 등급
    CONFIDENCE_LEVELS = {
        "HIGH": 0.7,
        "MEDIUM": 0.4,
        "LOW": 0.2,
    }

    def __init__(self):
        """초기화"""
        self.logger = logging.getLogger(__name__)

    def recalibrate_confidence(
        self,
        original_confidence: float,
        validation_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """원래 신뢰도를 실제 검증 결과로 조정

        Args:
            original_confidence: LLM이 부여한 원래 신뢰도 (0-1)
            validation_results: 검증 결과
                - entity_exists: bool (엔티티 존재 여부)
                - intent_pattern_matched: bool (Intent 패턴 매칭 여부)
                - fallback_used: bool (Fallback 사용 여부)
                - result_count: int (반환 결과 수)

        Returns:
            recalibrated_confidence: 조정된 신뢰도 (0-1)
            adjustment_factors: 적용된 조정 팩터들
            final_level: "HIGH" / "MEDIUM" / "LOW"
        """

        adjusted_confidence = original_confidence
        adjustment_factors = {}

        # 1. 엔티티 매칭 확인
        if validation_results.get("entity_exists"):
            adjustment_factors["entity_match"] = self.CONFIDENCE_ADJUSTMENTS["entity_match"]
            adjusted_confidence += adjustment_factors["entity_match"]
        else:
            adjustment_factors["entity_mismatch"] = self.CONFIDENCE_ADJUSTMENTS["entity_mismatch"]
            adjusted_confidence += adjustment_factors["entity_mismatch"]

        # 2. Intent 패턴 매칭
        if validation_results.get("intent_pattern_matched"):
            adjustment_factors["pattern_match"] = self.CONFIDENCE_ADJUSTMENTS["pattern_match"]
            adjusted_confidence += adjustment_factors["pattern_match"]

        # 3. Fallback 사용 여부
        if validation_results.get("fallback_used"):
            adjustment_factors["fallback_used"] = self.CONFIDENCE_ADJUSTMENTS["fallback_used"]
            adjusted_confidence += adjustment_factors["fallback_used"]

        # 4. 결과 개수
        result_count = validation_results.get("result_count", 0)
        if result_count == 0:
            adjustment_factors["zero_results"] = self.CONFIDENCE_ADJUSTMENTS["zero_results"]
            adjusted_confidence += adjustment_factors["zero_results"]

        # 신뢰도를 0-1 범위로 제한
        adjusted_confidence = max(0.0, min(adjusted_confidence, 1.0))

        # 신뢰도 등급 결정
        final_level = self._get_confidence_level(adjusted_confidence)

        self.logger.debug(
            "Confidence recalibrated",
            extra={
                "original": round(original_confidence, 2),
                "adjusted": round(adjusted_confidence, 2),
                "level": final_level,
                "adjustments": adjustment_factors,
            },
        )

        return {
            "original_confidence": original_confidence,
            "recalibrated_confidence": adjusted_confidence,
            "adjustment_factors": adjustment_factors,
            "total_adjustment": adjusted_confidence - original_confidence,
            "final_level": final_level,
        }

    def _get_confidence_level(self, confidence: float) -> str:
        """신뢰도 값을 등급으로 변환"""
        if confidence >= self.CONFIDENCE_LEVELS["HIGH"]:
            return "HIGH"
        elif confidence >= self.CONFIDENCE_LEVELS["MEDIUM"]:
            return "MEDIUM"
        else:
            return "LOW"

    def apply_confidence_penalty(
        self,
        confidence: float,
        penalty_reason: str,
        penalty_amount: float = 0.2,
    ) -> float:
        """특정 사유로 신뢰도 페널티 적용

        Args:
            confidence: 현재 신뢰도
            penalty_reason: 페널티 사유
            penalty_amount: 페널티 크기 (기본 0.2)

        Returns:
            페널티가 적용된 신뢰도
        """
        penalized = confidence - penalty_amount
        penalized = max(0.0, min(penalized, 1.0))

        self.logger.info(
            f"Confidence penalty applied",
            extra={
                "original": round(confidence, 2),
                "penalized": round(penalized, 2),
                "reason": penalty_reason,
                "penalty_amount": penalty_amount,
            },
        )

        return penalized

    def apply_confidence_boost(
        self,
        confidence: float,
        boost_reason: str,
        boost_amount: float = 0.15,
    ) -> float:
        """특정 사유로 신뢰도 부스트 적용

        Args:
            confidence: 현재 신뢰도
            boost_reason: 부스트 사유
            boost_amount: 부스트 크기 (기본 0.15)

        Returns:
            부스트가 적용된 신뢰도
        """
        boosted = confidence + boost_amount
        boosted = max(0.0, min(boosted, 1.0))

        self.logger.info(
            f"Confidence boost applied",
            extra={
                "original": round(confidence, 2),
                "boosted": round(boosted, 2),
                "reason": boost_reason,
                "boost_amount": boost_amount,
            },
        )

        return boosted
