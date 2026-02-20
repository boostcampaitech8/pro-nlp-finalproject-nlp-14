"""MIT Search 도구 실행 노드"""

import logging

from langchain_core.runnables import RunnableConfig

from app.infrastructure.graph.workflows.mit_mention.state import MitMentionState
from app.infrastructure.graph.workflows.mit_search.graph import mit_search_graph

logger = logging.getLogger(__name__)


async def execute_search(state: MitMentionState, config: RunnableConfig = None) -> dict:
    """MIT Search 도구 실행 (검색 필요 시에만 호출)

    Contract:
        reads: mit_mention_search_query, mit_mention_content
        writes: mit_mention_search_results
        side-effects: MIT Search 서브그래프 실행
        failures: 검색 실패 시 빈 결과 반환
    """
    search_query = state.get("mit_mention_search_query") or state.get("mit_mention_content", "")

    if not search_query:
        logger.warning("[execute_search] No search query provided")
        return {"mit_mention_search_results": None}

    logger.info(f"[execute_search] Executing MIT Search: query={search_query[:50]}...")

    try:
        # MIT Search 서브그래프 실행
        search_result = await mit_search_graph.ainvoke({
            "mit_search_query": search_query,
            "messages": [],  # MIT Mention은 단일 쿼리이므로 빈 메시지
            "user_id": "mention_workflow",  # 워크플로우 식별용
        }, config=config)

        # 검색 결과 추출
        final_results = search_result.get("mit_search_raw_results", [])

        if final_results:
            # 결과를 텍스트로 포맷팅
            result_text = "[검색 결과]\n"
            for idx, item in enumerate(final_results[:7], 1):  # 상위 5개→7개로 확대
                title = item.get("title", "제목 없음")
                content_preview = item.get("content", "")[:250]  # 150→250자로 확대
                score = item.get("final_score", item.get("metadata", {}).get("score", 0))
                result_text += f"{idx}. {title} (점수: {score:.2f})\n   {content_preview}...\n\n"

            logger.info(f"[execute_search] Search successful: {len(final_results)} results")
            return {"mit_mention_search_results": result_text}

        logger.warning("[execute_search] No search results found")
        return {"mit_mention_search_results": "[검색 결과] 관련 정보를 찾지 못했습니다."}

    except Exception as e:
        logger.exception(f"[execute_search] Search failed: {e}")
        return {"mit_mention_search_results": f"[검색 오류] {str(e)}"}
