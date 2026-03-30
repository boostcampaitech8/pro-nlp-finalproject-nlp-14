"""Clova Studio Reranker API를 사용한 결과 품질 향상을 위한 리랭킹 노드."""

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.core.config import get_settings

from ..state import MitSearchState

logger = logging.getLogger(__name__)

# ============================================================================
# Reranking Configuration
# ============================================================================

CLOVA_RERANKER_ENDPOINT = "https://clovastudio.stream.ntruss.com/v1/api-tools/reranker"
FULLTEXT_WEIGHT = 0.6
SEMANTIC_WEIGHT = 0.4


async def _call_clova_reranker(
    query: str, documents: list[dict[str, str]]
) -> list[dict[str, Any]] | None:
    """Clova Studio Reranker API 호출.

    Args:
        query: 검색 쿼리
        documents: [{"id": "...", "doc": "..."}] 형식의 문서 리스트

    Returns:
        API 응답 결과 또는 None (실패 시)
    """
    settings = get_settings()
    api_key = settings.ncp_clovastudio_api_key

    if not api_key:
        logger.warning("NCP_CLOVASTUDIO_API_KEY not configured")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "documents": documents,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                CLOVA_RERANKER_ENDPOINT,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            # API 응답에서 결과 추출
            # Clova Reranker는 result.data.rankedResults 형태로 반환
            if "result" in result and "rankedResults" in result.get("result", {}):
                return result["result"]["rankedResults"]
            elif "rankedResults" in result:
                return result["rankedResults"]
            elif "data" in result:
                return result["data"]
            else:
                logger.warning(f"Unexpected Clova Reranker response format: {result}")
                return None

    except httpx.HTTPStatusError as e:
        logger.error(f"Clova Reranker API HTTP error: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Clova Reranker API error: {e}")
        return None


async def reranker_async(state: MitSearchState) -> dict[str, Any]:
    """Clova Studio Reranker API를 사용하여 원시 결과 재순위화.

    Contract:
        reads: mit_search_raw_results, mit_search_query, mit_search_query_intent
        writes: mit_search_ranked_results (final_score 포함)
        side-effects: Clova Reranker API 호출, 의도 기반 가중치 적응
        failures: API 미설정/오류 → FULLTEXT만 사용하여 폴백

    쿼리 의도(intent)와 포커스(focus)를 반영한 적응형 가중치로 재순위화.
    """
    logger.info("Starting reranking with Clova Studio Reranker API")

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

        # Clova Reranker API용 문서 준비
        documents = []
        for i, result in enumerate(raw_results):
            # 결과 텍스트 준비 - graph_context 우선 사용
            result_text = result.get('graph_context') or f"{result.get('title', '')} {result.get('content', '')}"
            result_text = result_text[:4096]  # API 제한 고려

            documents.append({
                "id": str(i),
                "doc": result_text,
            })

        # Clova Reranker API 호출
        rerank_results = await _call_clova_reranker(query, documents)

        if rerank_results is None:
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
            logger.info("[Reranking] Entity search mode: semantic 90% / fulltext 10%")
        else:
            semantic_weight = 0.4
            fulltext_weight = 0.6
            logger.info("[Reranking] General search mode: semantic 40% / fulltext 60%")

        # API 결과를 점수 맵으로 변환
        rerank_score_map = {}
        for item in rerank_results:
            doc_id = str(item.get("id", item.get("index", "")))
            # Clova API 응답 형식에 따라 score 필드명이 다를 수 있음
            score = item.get("score", item.get("relevance_score", item.get("rank_score", 0)))
            rerank_score_map[doc_id] = score

        # 재순위화 점수 계산
        ranked_results = []

        for i, result in enumerate(raw_results):
            try:
                # Clova Reranker 점수 (0~1 범위로 정규화)
                rerank_score = rerank_score_map.get(str(i), 0)
                # 점수가 0~1 범위가 아니면 정규화
                if rerank_score > 1:
                    rerank_score = min(1, rerank_score / 100)

                # 최종 점수 = FULLTEXT(의도 무관) + Semantic(의도 반영)
                fulltext_score = result.get("score", 0.5)
                final_score = fulltext_weight * fulltext_score + semantic_weight * rerank_score

                ranked_results.append({
                    **result,
                    "rerank_score": rerank_score,
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
