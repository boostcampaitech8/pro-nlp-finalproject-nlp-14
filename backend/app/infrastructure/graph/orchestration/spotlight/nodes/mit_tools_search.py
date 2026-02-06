import logging

from ..state import SpotlightOrchestrationState
from app.infrastructure.graph.workflows.mit_search.graph import (
    mit_search_graph_from_cypher,
)

logger = logging.getLogger(__name__)


async def execute_mit_tools_search(state: SpotlightOrchestrationState) -> SpotlightOrchestrationState:
    """MIT-Tools 검색 실행 노드

    Contract:
        reads: messages, user_id, mit_search_query_intent, retry_count
        writes: tool_results
        side-effects: MIT Search 서브그래프 실행 (cypher_generator + tool_executor)
        failures: TOOL_EXECUTION_FAILED -> 빈 결과 반환

    MIT Search 서브그래프의 cypher 생성 및 실행 단계만 수행합니다.
    의도 분석(query_intent)은 이미 mit_tools_analyze에서 완료된 상태입니다.
    """
    logger.info("MIT-Tools 검색 실행 단계 진입")

    messages = state.get('messages', [])
    user_id = state.get('user_id', 'unknown')
    retry_count = state.get('retry_count', 0)
    next_subquery = state.get('next_subquery')  # Replanning에서 지정한 서브-쿼리

    # query_intent는 mit_tools_analyze에서 이미 분석됨
    query_intent = state.get('mit_search_query_intent', {})
    primary_entity = state.get('mit_search_primary_entity')

    # next_subquery가 있으면 (replanning 후) 그것을 사용, 아니면 원래 쿼리 사용
    if next_subquery:
        query = next_subquery
        logger.info(f"[Replanning] 서브-쿼리 사용: {query}")
    else:
        query = ""
        for msg in reversed(messages):
            if getattr(msg, "type", None) == "human":
                query = msg.content
                break

    if not query:
        last_msg_type = getattr(messages[-1], "type", None) if messages else None
        logger.warning(
            "검색 쿼리 비어있음: messages=%d, last_type=%s",
            len(messages),
            last_msg_type,
        )

    logger.info(
        f"검색 실행 쿼리: {query[:50]}..., "
        f"엔티티: {primary_entity}, 재시도: {retry_count}"
    )

    try:
        # MIT Search 서브그래프 실행 (cypher_generator부터)
        # pre-filled query_intent를 전달
        search_result = await mit_search_graph_from_cypher.ainvoke({
            "mit_search_query": query,
            "mit_search_query_intent": query_intent,  # 이미 분석된 의도
            "messages": messages,
            "user_id": user_id,
        })

        # 검색 결과 추출
        final_results = search_result.get("mit_search_raw_results", [])

        # 결과를 tool_results에 추가
        if final_results:
            result_summary = "\n[MIT Search 결과]\n"
            for idx, item in enumerate(final_results[:10], 1):
                title = item.get("title", "제목 없음")
                score = item.get("final_score", item.get("metadata", {}).get("score", 0))
                result_summary += f"{idx}. {title} (점수: {score:.2f})\n"

            logger.info(f"✓ MIT Search 성공: {len(final_results)}개 결과 반환")
            return SpotlightOrchestrationState(tool_results=result_summary)
        logger.warning("✗ MIT Search 결과 없음")
        return SpotlightOrchestrationState(tool_results="\n[MIT Search 결과] 검색 결과가 없습니다\n")

    except Exception as e:
        logger.error(f"MIT-Tools 검색 실행 중 오류: {e}", exc_info=True)
        return SpotlightOrchestrationState(tool_results=f"\n[MIT Search 오류] {str(e)}\n")
