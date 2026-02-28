"""응답 검증 노드"""

import logging
from typing import Literal

from app.infrastructure.graph.config import MAX_RETRY
from app.infrastructure.graph.workflows.mit_mention.state import (
    MitMentionState,
)

logger = logging.getLogger(__name__)


def _is_capability_question(content: str) -> bool:
    if not content:
        return False

    keywords = [
        "할 수 있는", "할수있는", "가능한", "뭐 할 수", "무엇을 할 수",
        "어떤 기능", "기능 알려", "기능 소개", "어떤 도움", "도와줄 수",
        "무슨 일", "무엇을 해", "무엇을 하", "도움이 되는",
    ]

    return any(k in content for k in keywords)


async def validate_response(state: MitMentionState) -> dict:
    """응답 품질 검증

    Contract:
        reads: mit_mention_raw_response, mit_mention_retry_count
        writes: mit_mention_validation, mit_mention_response, mit_mention_retry_count, mit_mention_retry_reason
        side-effects: None
        failures: None (always succeeds)
    """
    raw_response = state.get("mit_mention_raw_response", "")
    content = state.get("mit_mention_content", "")
    retry_count = state.get("mit_mention_retry_count", 0)

    # 기본 검증
    issues = []

    # 1. 길이 검증
    if len(raw_response) < 10:
        issues.append("응답이 너무 짧습니다")

    # 최대 길이 제한 제거 (응답 절단 방지) - 문장 완성을 우선시
    # 이전: > 2000자 제한으로 인한 불필요한 재시도
    # 현재: 최대 길이 제한 없음 (LLM의 자연스러운 응답 완성 보장)

    # 2. 내용 검증 (간단한 휴리스틱)
    if "죄송합니다" in raw_response and "오류" in raw_response:
        # 에러 메시지인 경우 통과 (재시도 무의미)
        pass
    elif raw_response.strip() == "":
        issues.append("빈 응답입니다")

    # 3. 기능 안내 질문 품질 검증
    if _is_capability_question(content):
        response_length = len(raw_response.strip())
        has_examples = any(key in raw_response for key in ["예:", "예시", "예를", "예시 질문"])
        bullet_lines = [
            line for line in raw_response.splitlines()
            if line.strip().startswith("-") or line.strip().startswith("*")
        ]
        has_enough_bullets = len(bullet_lines) >= 3

        if response_length < 120 or (not has_examples and not has_enough_bullets):
            issues.append("기능 안내가 충분하지 않습니다")

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
