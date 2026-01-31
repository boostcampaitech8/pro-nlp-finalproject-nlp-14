"""검색 전략 결정 로직 (독립적인 모듈)"""

import logging

logger = logging.getLogger(__name__)


class SearchStrategyRouter:
    """쿼리 정보 기반 검색 전략 결정 (신뢰도 기반 Fallback 포함)"""

    @staticmethod
    def determine_strategy(
        query_intent: dict,
        entity_types: list,
        normalized_keywords: str,
        user_id: str
    ) -> dict:
        """검색 전략을 결정합니다.

        신뢰도 기반 적응형 전략:
        - High confidence (>0.7): Text-to-Cypher만
        - Medium confidence (0.4-0.7): Text-to-Cypher + Template Fallback
        - Low confidence (<0.4): Template-based 우선

        Args:
            query_intent: query_intent_analyzer 출력 (intent_type, primary_entity, search_focus)
            entity_types: filter_extraction 출력의 entity_types
            normalized_keywords: 정규화된 검색어
            user_id: 사용자 ID

        Returns:
            {
                "strategy": "text_to_cypher" | "template_based",
                "search_term": "원본 쿼리",
                "reasoning": "전략 선택 이유",
                "use_fallback": True/False,
                "confidence": 0.0-1.0
            }
        """
        original_query = normalized_keywords if normalized_keywords else "*"
        confidence = query_intent.get("confidence", 0.5)
        intent_type = query_intent.get("intent_type", "general_search")
        search_focus = query_intent.get("search_focus")
        primary_entity = query_intent.get("primary_entity")

        # 🎯 Case 1: 단순 패턴 (template으로 충분) → Template 우선
        if _is_simple_pattern(intent_type, search_focus, primary_entity):
            return {
                "strategy": "template_based",
                "search_term": original_query,
                "reasoning": "Simple pattern detected - Template 우선 (Fallback: LLM)",
                "use_fallback": True,
                "confidence": confidence,
                "intent_type": intent_type,
                "search_focus": search_focus,
                "primary_entity": primary_entity,
            }

        # 🎯 Case 2: 높은 신뢰도 → Text-to-Cypher만
        if confidence > 0.7:
            return {
                "strategy": "text_to_cypher",
                "search_term": original_query,
                "reasoning": f"High confidence ({confidence:.2f}) - LLM Cypher 단독 사용",
                "use_fallback": False,
                "confidence": confidence
            }

        # 🎯 Case 3: 중간/낮은 신뢰도 → LLM 시도 + Template Fallback
        return {
            "strategy": "text_to_cypher",
            "search_term": original_query,
            "reasoning": f"Medium confidence ({confidence:.2f}) - LLM + Template Fallback",
            "use_fallback": True,
            "confidence": confidence
        }


def _is_simple_pattern(intent_type: str, search_focus: str, primary_entity: str) -> bool:
    """단순 패턴 감지 (Template으로 충분한 경우)"""
    # 명확한 엔티티 검색
    if intent_type == "entity_search" and primary_entity:
        if search_focus in ["Decision", "Meeting", "Action", "Team"]:
            return True

    # 복합 메타 검색 (템플릿 처리 가능)
    if intent_type == "meta_search" and search_focus == "Composite":
        return True

    # 시간 기반 검색
    if intent_type == "temporal_search" and search_focus in ["Meeting", "Decision"]:
        return True

    return False




# 사용 예시
"""
router = SearchStrategyRouter()
strategy = router.determine_strategy(
    query_intent={"intent_type": "entity_search", "primary_entity": "신수효", ...},
    entity_types=["Decision"],
    normalized_keywords="신수효",
    user_id="user-123"
)

# 모든 경우에 text_to_cypher 전략 사용
match strategy["strategy"]:
    case "text_to_cypher":
        # LLM 기반 Cypher 생성
        cypher = llm_based_cypher_generation(strategy["search_term"])
"""

