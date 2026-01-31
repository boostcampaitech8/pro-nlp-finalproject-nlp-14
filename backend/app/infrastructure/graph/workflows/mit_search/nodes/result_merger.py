"""검색 결과 병합 노드"""

import logging
from typing import Any

from app.infrastructure.graph.workflows.mit_search.state import MitSearchState

logger = logging.getLogger(__name__)


async def result_merger_async(state: MitSearchState) -> dict[str, Any]:
    """Cypher 검색 결과 병합 및 선택.

    Args:
        state: MIT Search 상태

    Returns:
        병합된 최종 결과
    """
    logger.info("[Result Merger] 결과 병합 시작")

    try:
        results = state.get("mit_search_raw_results", [])

        if results:
            logger.info(f"[Result Merger] Cypher 결과 {len(results)}개 사용")
            merge_strategy = "cypher_primary"
        else:
            logger.warning("[Result Merger] 검색 결과 없음")
            merge_strategy = "empty"

        return {
            "merged_results": results,
            "merge_strategy": merge_strategy,
        }

    except Exception as e:
        logger.error(f"[Result Merger] 에러: {str(e)}", exc_info=True)
        return {
            "merged_results": state.get("mit_search_raw_results", []),
            "merge_strategy": "error_fallback_cypher",
        }
