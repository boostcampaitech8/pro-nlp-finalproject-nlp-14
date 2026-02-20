"""검색 필요 여부 판단 노드 (Clova Router API 기반)"""

import logging

from app.infrastructure.graph.config import NCP_CLOVASTUDIO_API_KEY
from app.infrastructure.graph.workflows.mit_mention.state import MitMentionState

logger = logging.getLogger(__name__)

# Clova Router 설정
MENTION_ROUTER_ID = "l2q6n9us"  # MIT-Mention 전용 Router ID
MENTION_ROUTER_VERSION = 1


async def route_search_need(state: MitMentionState) -> dict:
    """검색 필요 여부 판단 노드 (Clova Router API 사용)

    Contract:
        reads: mit_mention_content
        writes: mit_mention_needs_search, mit_mention_search_query
        side-effects: Clova Router API 호출
    """
    from app.infrastructure.graph.integration.clova_router import ClovaRouterClient

    content = state.get("mit_mention_content", "")

    # 너무 짧은 입력은 검색 불필요
    if len(content.strip()) < 5:
        logger.info("[route_search_need] Too short, skip search")
        return {
            "mit_mention_needs_search": False,
            "mit_mention_search_query": None,
        }

    try:
        # Clova Router API 호출
        async with ClovaRouterClient(
            router_id=MENTION_ROUTER_ID,
            version=MENTION_ROUTER_VERSION,
            api_key=NCP_CLOVASTUDIO_API_KEY,
        ) as client:
            response = await client.route(query=content)

        # 도메인 결과 추출
        domain_result = response.get("result", {}).get("domain", {}).get("result", "")

        # "search needed" 도메인이면 검색 트리거
        needs_search = domain_result == "search needed"

        logger.info(
            f"[route_search_need] Clova Router: domain={domain_result}, "
            f"needs_search={needs_search}"
        )

        return {
            "mit_mention_needs_search": needs_search,
            "mit_mention_search_query": content if needs_search else None,
        }

    except Exception as e:
        logger.exception(f"[route_search_need] Clova Router failed: {e}")
        # Fallback: 키워드 기반 간단 판단
        keywords = ["누가", "누구", "어떤", "관련", "다른", "찾아", "어디", "언제"]
        needs_search = any(kw in content for kw in keywords) and len(content) > 10

        logger.warning(f"[route_search_need] Fallback to keyword-based: {needs_search}")

        return {
            "mit_mention_needs_search": needs_search,
            "mit_mention_search_query": content if needs_search else None,
        }
