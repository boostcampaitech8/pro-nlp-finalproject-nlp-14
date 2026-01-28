"""BGE Reranker를 사용한 결과 품질 향상을 위한 리랭킹 노드."""

import asyncio
import logging
from typing import Any, Optional

from ..state import MitSearchState

logger = logging.getLogger(__name__)

# ============================================================================
# Reranking Configuration (로컬 정의)
# ============================================================================

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_USE_FP16 = True
FULLTEXT_WEIGHT = 0.6
SEMANTIC_WEIGHT = 0.4

# BGE Reranker 싱글톤 (한 번만 로드)
_reranker_model: Optional[Any] = None
_reranker_load_attempted: bool = False


def _get_reranker_model():
    """BGE Reranker 모델을 싱글톤으로 로드."""
    global _reranker_model, _reranker_load_attempted

    if _reranker_load_attempted:
        return _reranker_model

    _reranker_load_attempted = True

    try:
        from FlagEmbedding import FlagReranker

        _reranker_model = FlagReranker(
            model_name_or_path=RERANKER_MODEL,
            use_fp16=RERANKER_USE_FP16
        )
        logger.info(f"BGE Reranker model '{RERANKER_MODEL}' loaded successfully (singleton)")
        return _reranker_model
    except ImportError:
        logger.warning("FlagEmbedding not installed. Install: pip install FlagEmbedding")
        return None
    except Exception:
        logger.error("Failed to load BGE Reranker model")
        return None


async def reranker_async(state: MitSearchState) -> dict[str, Any]:
    """BGE Reranker v2-m3 모델(싱글톤 로드)을 사용하여 원시 결과 재순위화.

    Contract:
        reads: mit_search_raw_results (FULLTEXT 점수가 포함된 리스트), mit_search_query
        writes: mit_search_ranked_results (결합된 final_score가 포함된 결과)
        side-effects: BGE 모델 추론 (CPU/GPU), 첫 호출 시 모델 싱글톤 로드
        failures: FlagEmbedding 미설치 OR 모델 추론 에러 → FULLTEXT 점수만 사용하여 폴백

    FULLTEXT 점수 (60%) + BGE reranker 점수 (40%)를 결합.
    FlagEmbedding 미설치 시 FULLTEXT 점수로 폴백.

    Returns:
        mit_search_ranked_results로 State 업데이트
    """
    logger.info("Starting reranking")

    try:
        raw_results = state.get("mit_search_raw_results", [])
        query = state.get("mit_search_query", "")

        if not raw_results:
            logger.info("No results to rerank")
            return {"mit_search_ranked_results": []}

        if not query:
            logger.warning("No query for reranking, returning original results")
            return {"mit_search_ranked_results": raw_results}

        # BGE Reranker 모델 로드 (싱글톤)
        reranker_model = _get_reranker_model()

        if reranker_model is None:
            logger.warning("Falling back to FULLTEXT scores only")
            # FULLTEXT 점수로만 정렬
            ranked_results = sorted(
                raw_results,
                key=lambda x: x.get("score", 0),
                reverse=True
            )
            return {"mit_search_ranked_results": ranked_results}

        # 재순위화 점수 계산
        ranked_results = []

        for result in raw_results:
            try:
                # 결과 텍스트 준비
                result_text = f"{result.get('title', '')} {result.get('content', '')}"[:512]  # 최대 512자

                # BGE Reranker로 관련도 점수 계산 (0-1)
                rerank_score = reranker_model.compute_score([query, result_text])

                # 정규화 (BGE는 음수 점수도 가능하므로 0-1로 정규화)
                rerank_score_normalized = max(0, min(1, (rerank_score + 1) / 2))

                # 최종 점수 계산 (가중 평균)
                fulltext_score = result.get("score", 0.5)
                final_score = (fulltext_score * FULLTEXT_WEIGHT +
                              rerank_score_normalized * SEMANTIC_WEIGHT)

                ranked_results.append({
                    **result,
                    "rerank_score": rerank_score_normalized,
                    "final_score": final_score
                })

            except Exception:
                logger.warning(f"Reranking failed for result {result.get('id')}")
                # 재순위화 실패 시 원본 점수 사용
                ranked_results.append({
                    **result,
                    "rerank_score": 0,
                    "final_score": result.get("score", 0.5)
                })

        # 최종 점수로 정렬
        ranked_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        logger.info(f"Reranked {len(ranked_results)} results")
        logger.debug(f"Top result score: {ranked_results[0].get('final_score', 0):.3f}" if ranked_results else "No results")

        return {"mit_search_ranked_results": ranked_results}

    except Exception:
        logger.error("Reranking failed", exc_info=True)
        # 실패 시 원본 결과 그대로 반환
        return {"mit_search_ranked_results": state.get("mit_search_raw_results", [])}


def reranker(state: MitSearchState) -> dict[str, Any]:
    """동기 테스트용 래퍼."""
    return asyncio.run(reranker_async(state))
