"""Clova Router 응답 매핑 로직

Clova Studio Router API의 도메인 분류 결과를
SimpleRouterOutput 형식으로 변환합니다.
"""

import logging

from app.infrastructure.graph.orchestration.shared.simple_router import SimpleRouterOutput

logger = logging.getLogger(__name__)


class RouterResponseMapper:
    """Clova Router API 응답을 SimpleRouterOutput으로 매핑

    Clova Router의 도메인 분류 결과를 기존 Simple Query Router의
    카테고리 체계로 변환하여 하위 호환성을 보장합니다.

    도메인 매핑 규칙 (실제 Clova Router rdtl7tve 모델 기준):
        - "simple talk" → simple_talk (간단한 쿼리, Planning 스킵)
        - "planning needed" → planning_needed (복잡한 쿼리, Planning 필요)
        - "" (빈 문자열) → other (복잡한 쿼리)
    """

    # Clova 도메인 → SimpleRouter 카테고리 매핑
    DOMAIN_TO_CATEGORY = {
        "simple talk": "simple_talk",  # 간단한 대화 (인사, 감사, 잡담 등)
        "planning needed": "planning_needed",  # 복잡한 쿼리 (업무, 지식 등)
    }

    # 간단한 쿼리로 판단할 카테고리 (Planning 스킵)
    SIMPLE_CATEGORIES = {"simple_talk"}

    @classmethod
    def map_response(cls, clova_response: dict, query: str) -> SimpleRouterOutput:
        """Clova Router 응답을 SimpleRouterOutput으로 변환

        Args:
            clova_response: Clova Router API 응답
            query: 원본 쿼리 (로깅 및 응답 생성용)

        Returns:
            SimpleRouterOutput: 표준화된 라우터 출력

        Example:
            >>> clova_response = {
            ...     "status": {"code": "20000", "message": "OK"},
            ...     "result": {
            ...         "domain": {"result": "greeting", "called": True},
            ...         "blockedContent": {"result": [], "called": True},
            ...         "safety": {"result": [], "called": True},
            ...         "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15}
            ...     }
            ... }
            >>> output = RouterResponseMapper.map_response(clova_response, "안녕하세요")
            >>> output.is_simple_query
            True
            >>> output.category
            'greeting'
        """
        result = clova_response.get("result", {})
        domain_data = result.get("domain", {})
        domain_result = domain_data.get("result", "other")

        # 도메인 → 카테고리 매핑
        category = cls.DOMAIN_TO_CATEGORY.get(domain_result, "other")

        # is_simple_query 판단: greeting/sentiment/acknowledgment/nonsense만 간단
        is_simple = category in cls.SIMPLE_CATEGORIES

        # 신뢰도 계산 (Clova는 명시적 confidence 없으므로 추정)
        # - 도메인이 매핑 테이블에 있으면 높은 신뢰도 (0.95)
        # - 없으면 중간 신뢰도 (0.5)
        confidence = 0.95 if domain_result in cls.DOMAIN_TO_CATEGORY else 0.5

        # 콘텐츠 필터 및 세이프티 필터 확인
        blocked_content = result.get("blockedContent", {}).get("result", [])
        safety_issues = result.get("safety", {}).get("result", [])

        # 필터링된 경우 신뢰도 조정
        if blocked_content or safety_issues:
            logger.warning(
                f"Clova Router 필터 감지: blocked={blocked_content}, safety={safety_issues}"
            )
            # 필터링된 경우 unavailable 카테고리로 변경
            category = "unavailable"
            is_simple = False
            confidence = 0.9

        # simple_response 생성 (간단한 쿼리일 경우)
        simple_response = cls._generate_simple_response(category, query) if is_simple else None

        # reasoning 생성
        reasoning = f"Clova Router 판정: domain={domain_result} → category={category}"
        if blocked_content:
            reasoning += f" (blocked: {blocked_content})"
        if safety_issues:
            reasoning += f" (safety: {safety_issues})"

        logger.debug(
            f"Router 매핑: domain={domain_result}, category={category}, "
            f"is_simple={is_simple}, confidence={confidence:.2f}"
        )

        return SimpleRouterOutput(
            is_simple_query=is_simple,
            category=category,
            simple_response=simple_response,
            confidence=confidence,
            reasoning=reasoning,
        )

    @staticmethod
    def _generate_simple_response(category: str, query: str) -> str | None:
        """간단한 응답 생성 (카테고리별 기본 응답)

        Args:
            category: 쿼리 카테고리
            query: 원본 쿼리

        Returns:
            카테고리별 기본 응답 또는 None

        Note:
            이 응답은 참고용이며, 실제 응답은 answering 노드에서 생성됩니다.
        """
        if category == "simple_talk":
            # 간단한 대화 - answering 노드에서 적절히 처리됨
            return None
        else:
            return None
