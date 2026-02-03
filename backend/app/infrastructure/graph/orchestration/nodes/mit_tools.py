import logging

from app.infrastructure.graph.orchestration.state import OrchestrationState
from app.infrastructure.graph.workflows.mit_search.graph import mit_search_graph

logger = logging.getLogger(__name__)


async def execute_mit_tools(state: OrchestrationState) -> OrchestrationState:
    """MIT-Tools 실행 노드

    Contract:
        reads: messages, user_id, plan, retry_count
        writes: tool_results
        side-effects: MIT Search 서브그래프 실행
        failures: TOOL_EXECUTION_FAILED -> 빈 결과 반환

    MIT Search 서브그래프를 호출하여 Knowledge Graph에서 검색을 수행합니다.
    """
    logger.info("MIT-Tools 단계 진입")

    messages = state.get('messages', [])
    user_id = state.get('user_id', 'unknown')
    retry_count = state.get('retry_count', 0)
    next_subquery = state.get('next_subquery')  # Replanning에서 지정한 서브-쿼리
    
    # next_subquery가 있으면 (replanning 후) 그것을 사용, 아니면 원래 쿼리 사용
    if next_subquery:
        query = next_subquery
        logger.info(f"[Replanning] 서브-쿼리 사용: {query}")
    else:
        query = messages[-1].content if messages else ""

    logger.info(f"쿼리: {query[:50]}..., 사용자: {user_id}, 재시도: {retry_count}")

    try:
        # MIT Search 서브그래프 실행
        search_result = await mit_search_graph.ainvoke({
            "mit_search_query": query,  # 핵심: 쿼리 전달
            "messages": messages,
            "user_id": user_id,
        })

        # 검색 결과 추출
        final_results = search_result.get("mit_search_raw_results", [])
        
        # 결과를 tool_results에 추가
        if final_results:
            result_summary = f"\n[MIT Search 결과]\n"
            for idx, item in enumerate(final_results[:10], 1):
                title = item.get("title", "제목 없음")
                score = item.get("final_score", item.get("metadata", {}).get("score", 0))
                result_summary += f"{idx}. {title} (점수: {score:.2f})\n"
            
            logger.info(f"✓ MIT Search 성공: {len(final_results)}개 결과 반환")
            return OrchestrationState(tool_results=result_summary)
        logger.warning("✗ MIT Search 결과 없음")
        return OrchestrationState(tool_results="\n[MIT Search 결과] 검색 결과가 없습니다\n")

    except Exception as e:
        logger.error(f"MIT-Tools 실행 중 오류: {e}", exc_info=True)
        return OrchestrationState(tool_results=f"\n[MIT Search 오류] {str(e)}\n")
