"""응답 검증 노드"""

import logging
from typing import Literal

from app.infrastructure.graph.config import MAX_RETRY
from app.infrastructure.graph.workflows.mit_mention.state import (
    MitMentionState,
)

logger = logging.getLogger(__name__)


async def validate_response(state: MitMentionState) -> dict:
    """응답 품질 검증

    Contract:
        reads: mit_mention_raw_response, mit_mention_retry_count
        writes: mit_mention_validation, mit_mention_response, mit_mention_retry_count, mit_mention_retry_reason
        side-effects: None
        failures: None (always succeeds)
    """
    raw_response = state.get("mit_mention_raw_response", "")
    retry_count = state.get("mit_mention_retry_count", 0)

    # 기본 검증
    issues = []

    # 1. 길이 검증
    if len(raw_response) < 10:
        issues.append("응답이 너무 짧습니다")

    if len(raw_response) > 2000:
        issues.append("응답이 너무 깁니다")

    # 2. 내용 검증 (간단한 휴리스틱)
    if "죄송합니다" in raw_response and "오류" in raw_response:
        # 에러 메시지인 경우 통과 (재시도 무의미)
        pass
    elif raw_response.strip() == "":
        issues.append("빈 응답입니다")

    # 결과 판정
    passed = len(issues) == 0

    validation_result = {
        "passed": passed,
        "issues": issues,
    }

    if passed:
        logger.info("[validate_response] Validation passed")
        return {
            "mit_mention_validation": validation_result,
            "mit_mention_response": raw_response,
            "mit_mention_retry_count": retry_count,
        }
    else:
        new_retry_count = retry_count + 1
        logger.warning(f"[validate_response] Validation failed: {issues}, retry={new_retry_count}")

        # 최대 재시도 초과 시 그냥 통과
        if new_retry_count > MAX_RETRY:
            logger.info("[validate_response] Max retry exceeded, accepting response")
            return {
                "mit_mention_validation": {"passed": True, "issues": [], "forced": True},
                "mit_mention_response": raw_response,
                "mit_mention_retry_count": new_retry_count,
            }

        return {
            "mit_mention_validation": validation_result,
            "mit_mention_retry_count": new_retry_count,
            "mit_mention_retry_reason": "; ".join(issues),
        }


def route_validation(state: MitMentionState) -> Literal["generator", "end"]:
    """검증 결과에 따른 라우팅

    Contract:
        reads: mit_mention_validation
        returns: "generator" (재생성) 또는 "end" (완료)
    """
    validation = state.get("mit_mention_validation") or {}

    if validation.get("passed", False):
        return "end"

    return "generator"
