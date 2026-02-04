"""지식 그래프 검색 노드"""

import logging

from app.infrastructure.graph.workflows.mit_mention.state import MitMentionState
from app.infrastructure.graph.workflows.mit_search.graph import mit_search_graph

logger = logging.getLogger(__name__)


async def search_knowledge_graph(state: MitMentionState) -> dict:
    """MIT-Search 서브그래프를 호출하여 관련 지식 검색

    Contract:
        reads: mit_mention_search_query, mit_mention_content
        writes: mit_mention_search_results
        side-effects: MIT-Search 서브그래프 실행 (Neo4j 쿼리)
        failures: SEARCH_FAILED → 빈 결과 반환
    """
    search_query = state.get("mit_mention_search_query")
    content = state.get("mit_mention_content", "")

    if not search_query:
        logger.warning("[search_knowledge_graph] No search query provided")
        return {"mit_mention_search_results": []}

    logger.info(f"[search_knowledge_graph] Searching: {search_query[:50]}...")

    try:
        # MIT-Search 서브그래프 실행
        search_result = await mit_search_graph.ainvoke({
            "mit_search_query": search_query,
            "message": content,  # Fallback for messages
            "user_id": "system",  # Mention workflow는 user_id가 state에 없으므로 system 사용
        })

        # 검색 결과 추출
        raw_results = search_result.get("mit_search_raw_results", [])

        # 결과 필터링 및 포맷팅 (상위 5개만, 관련도 순)
        filtered_results = []
        for item in raw_results[:5]:  # 최대 5개만 사용
            filtered_results.append({
                "type": item.get("type", "Unknown"),
                "title": item.get("title", "제목 없음"),
                "content": item.get("content", "")[:200],  # 200자로 제한
                "score": item.get("final_score", item.get("score", 0)),
                "metadata": item.get("metadata", {}),
            })

        logger.info(f"[search_knowledge_graph] Found {len(filtered_results)} results")

        return {"mit_mention_search_results": filtered_results}

    except Exception as e:
        logger.exception(f"[search_knowledge_graph] Search failed: {e}")
        return {"mit_mention_search_results": []}
