"""BGE Reranker를 사용한 결과 품질 향상을 위한 리랭킹 노드."""

import asyncio
import logging
from typing import Any, Optional

from ..state import MitSearchState
from ..utils.score_calculator import ScoreCalculator

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
        reads: mit_search_raw_results, mit_search_query, mit_search_query_intent
        writes: mit_search_ranked_results (final_score 포함)
        side-effects: BGE 모델 추론, 의도 기반 가중치 적응
        failures: 모델 미설치 → FULLTEXT만 사용하여 폴백

    쿼리 의도(intent)와 포커스(focus)를 반영한 적응형 가중치로 재순위화.
    """
    logger.info("Starting reranking with intent-aware weighting")

    try:
        raw_results = state.get("mit_search_raw_results", [])
        query = state.get("mit_search_query", "")
        query_intent = state.get("mit_search_query_intent", {})

        if not raw_results:
            logger.info("No results to rerank")
            return {"mit_search_ranked_results": []}

        if not query:
            logger.warning("No query for reranking, returning original results")
            ranked_results = [
                {**result, "final_score": result.get("score", 0)}
                for result in raw_results
            ]
            return {"mit_search_ranked_results": ranked_results}

        # 쿼리 의도 추출
        search_focus = query_intent.get("search_focus")
        primary_entity = query_intent.get("primary_entity")
        intent_type = query_intent.get("intent_type", "general_search")

        logger.info(
            "[Reranking] 의도 기반 가중치 적용",
            extra={"focus": search_focus, "intent": intent_type},
        )

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
            # final_score 추가 (FULLTEXT 점수와 동일)
            ranked_results = [
                {**result, "final_score": result.get("score", 0)}
                for result in ranked_results
            ]
            return {"mit_search_ranked_results": ranked_results}

        # 의도 기반 가중치 결정
        # entity_search: 의도 명확 → semantic 높음 (90%)
        # general_search: 의도 불명확 → semantic 낮음 (40%)
        if intent_type == "entity_search" and primary_entity:
            semantic_weight = 0.9
            fulltext_weight = 0.1
            logger.info(f"[Reranking] Entity search mode: semantic 90% / fulltext 10%")
        else:
            semantic_weight = 0.4
            fulltext_weight = 0.6
            logger.info(f"[Reranking] General search mode: semantic 40% / fulltext 60%")

        # 재순위화 점수 계산
        ranked_results = []

        for result in raw_results:
            try:
                # 결과 텍스트 준비 - graph_context 우선 사용
                result_text = result.get('graph_context') or f"{result.get('title', '')} {result.get('content', '')}"
                result_text = result_text[:512]

                # BGE Reranker로 의미론적 관련도 점수
                rerank_scores = reranker_model.compute_score([query, result_text])
                rerank_score = rerank_scores[0] if isinstance(rerank_scores, list) else rerank_scores

                # 정규화 (BGE: -15~+15 → 0~1)
                rerank_score_normalized = max(0, min(1, (rerank_score + 15) / 30))

                # 최종 점수 = FULLTEXT(의도 무관) + Semantic(의도 반영)
                fulltext_score = result.get("score", 0.5)
                final_score = fulltext_weight * fulltext_score + semantic_weight * rerank_score_normalized

                ranked_results.append({
                    **result,
                    "rerank_score": rerank_score_normalized,
                    "final_score": final_score
                })

            except Exception:
                logger.warning(f"Reranking failed for result {result.get('id')}")
                ranked_results.append({
                    **result,
                    "rerank_score": 0,
                    "final_score": result.get("score", 0.5)
                })

        # 최종 점수로 정렬
        ranked_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)

        logger.info(
            f"Reranked {len(ranked_results)} results",
            extra={
                "top_score": ranked_results[0].get("final_score", 0) if ranked_results else 0,
                "focus": search_focus,
            },
        )

        return {"mit_search_ranked_results": ranked_results}

    except Exception:
        logger.error("Reranking failed", exc_info=True)
        # 실패 시 원본 결과 그대로 반환
        return {"mit_search_ranked_results": state.get("mit_search_raw_results", [])}


def reranker(state: MitSearchState) -> dict[str, Any]:
    """동기 테스트용 래퍼."""
    return asyncio.run(reranker_async(state))
