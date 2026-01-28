"""최종 결과 필터링을 위한 Selection 노드."""

import asyncio
import logging

from app.infrastructure.graph.config import get_graph_settings

from ..state import MitSearchState

logger = logging.getLogger(__name__)


async def selector_async(state: MitSearchState) -> dict:
    """오케스트레이션 레이어 사용을 위한 최종 결과 선택 및 포맷팅.

    Contract:
        reads: mit_search_ranked_results (final_score를 포함한 랭킹된 리스트)
        writes: mit_search_results (오케스트레이션으로의 최종 출력)
        side-effects: 필터링, 중복 제거, 포맷팅 (외부 호출 없음)
        failures: 빈 ranked_results → 빈 리스트 반환, 계속 진행

    적용 항목:
    - Top K 필터링 (기본값: 5)
    - 최소 점수 임계값 (0.3)
    - 중복 제거
    - 다운스트림 사용을 위한 포맷

    Returns:
        mit_search_results로 state 업데이트 (최종 출력)
    """
    logger.info("Starting result selection")

    try:
        ranked_results = state.get("mit_search_ranked_results", [])

        if not ranked_results:
            logger.info("No ranked results to select")
            return {"mit_search_results": []}

        # Config에서 설정값 로드
        settings = get_graph_settings()
        top_k = settings.mit_search_top_k
        min_score = settings.mit_search_min_score

        # Apply threshold and limit
        selected = [
            result for result in ranked_results
            if result.get("final_score", 0) >= min_score
        ][:top_k]

        # Format for orchestration
        formatted_results = []
        seen_ids = set()

        for result in selected:
            result_id = result.get("id")
            if result_id in seen_ids:
                continue

            seen_ids.add(result_id)
            formatted_results.append({
                "type": result.get("type", "decision"),
                "id": result_id,
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "metadata": {
                    "meeting_id": result.get("meeting_id"),
                    "meeting_title": result.get("meeting_title"),
                    "decided_at": result.get("decided_at"),
                    "score": result.get("final_score", 0)
                }
            })

        logger.info(f"Selected {len(formatted_results)} final results")

        return {"mit_search_results": formatted_results}

    except Exception as e:
        logger.error(f"Selection failed: {e}", exc_info=True)
        return {"mit_search_results": []}


def selector(state: MitSearchState) -> dict:
    """동기 테스트용 래퍼."""
    return asyncio.run(selector_async(state))
