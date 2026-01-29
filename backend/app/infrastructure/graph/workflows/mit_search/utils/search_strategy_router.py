"""검색 전략 결정 로직 (독립적인 모듈)"""

import logging

logger = logging.getLogger(__name__)


class SearchStrategyRouter:
    """쿼리 정보 기반 검색 전략 결정"""

    @staticmethod
    def determine_strategy(
        query_intent: dict,
        entity_types: list,
        normalized_keywords: str,
        user_id: str
    ) -> dict:
        """검색 전략을 결정합니다.

        모든 검색을 Text-to-Cypher LLM 기반으로 통일합니다.

        Args:
            query_intent: query_intent_analyzer 출력 (intent_type, primary_entity, search_focus)
            entity_types: filter_extraction 출력의 entity_types
            normalized_keywords: 정규화된 검색어
            user_id: 사용자 ID

        Returns:
            {
                "strategy": "text_to_cypher",
                "search_term": "원본 쿼리",
                "reasoning": "Text-to-Cypher LLM 검색"
            }
        """
        # 모든 검색을 Text-to-Cypher로 통일
        original_query = normalized_keywords if normalized_keywords else "*"
        
        return {
            "strategy": "text_to_cypher",
            "search_term": original_query,
            "reasoning": "Text-to-Cypher LLM 기반 검색"
        }




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

