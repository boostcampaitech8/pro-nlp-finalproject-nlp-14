"""Speculative RAG 결과 병합 노드"""

import logging
from typing import Any

from app.infrastructure.graph.workflows.mit_search.state import MitSearchState

logger = logging.getLogger(__name__)


async def result_merger_async(state: MitSearchState) -> dict[str, Any]:
    """Cypher와 벡터 검색 결과 병합 및 선택
    
    병합 전략:
    1. 벡터 검색이 빨리 완료되면 먼저 확인
    2. 신뢰도 > 0.8이면 벡터 결과 사용 (Cypher 기다리지 않음)
    3. 신뢰도 <= 0.8이면 Cypher 결과 대기
    4. 둘 다 있으면 스코어 기반 선택
    
    Args:
        state: MIT Search 상태
        
    Returns:
        병합된 최종 결과
    """
    logger.info("[Result Merger] 결과 병합 시작")
    
    try:
        cypher_results = state.get("cypher_results", [])
        vector_results = state.get("vector_search_results", [])
        vector_confidence = state.get("vector_confidence", 0.0)
        
        # 전략 1: 벡터 검색 신뢰도가 높으면 즉시 사용
        if vector_confidence > 0.8 and vector_results:
            logger.info(
                f"[Result Merger] 벡터 검색 신뢰도 높음 ({vector_confidence:.2f}) "
                f"→ 벡터 결과 사용"
            )
            merged_results = vector_results
            merge_strategy = "vector_high_confidence"
        
        # 전략 2: Cypher 결과 우선 (더 정확)
        elif cypher_results:
            logger.info(
                f"[Result Merger] Cypher 결과 {len(cypher_results)}개 사용"
            )
            merged_results = cypher_results
            merge_strategy = "cypher_primary"
        
        # 전략 3: 벡터 검색만 있으면 사용
        elif vector_results:
            logger.info(
                f"[Result Merger] 벡터 검색만 가능 ({vector_confidence:.2f}) "
                f"→ 벡터 결과 {len(vector_results)}개 사용"
            )
            merged_results = vector_results
            merge_strategy = "vector_fallback"
        
        # 전략 4: 둘 다 없으면 빈 결과
        else:
            logger.warning("[Result Merger] 검색 결과 없음")
            merged_results = []
            merge_strategy = "empty"
        
        return {
            "merged_results": merged_results,
            "merge_strategy": merge_strategy,
            "vector_used": merge_strategy.startswith("vector"),
        }
        
    except Exception as e:
        logger.error(f"[Result Merger] 에러: {str(e)}", exc_info=True)
        return {
            "merged_results": state.get("cypher_results", []),
            "merge_strategy": "error_fallback_cypher",
            "vector_used": False,
        }
