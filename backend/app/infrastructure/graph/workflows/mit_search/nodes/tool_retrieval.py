"""Neo4j 검색 실행을 위한 Tool retrieval 노드."""

import asyncio
import logging

from ..state import MitSearchState
from ..tools.search_tools import execute_cypher_search_async

logger = logging.getLogger(__name__)


async def tool_executor_async(state: MitSearchState) -> dict:
    """Neo4j에 대해 생성된 Cypher 쿼리를 실행하고 원본 결과 가져오기.

    Contract:
        reads: mit_search_cypher, mit_search_query, mit_search_filters, user_id
        writes: mit_search_raw_results (점수가 포함된 매칭 레코드 리스트)
        side-effects: Neo4j execute_cypher_search 호출 (외부 DB 쿼리)
        failures: Neo4j 타임아웃/연결 오류 → 빈 리스트 반환, 에러 로깅
    """
    logger.info("Starting tool execution")

    try:
        cypher = state.get("mit_search_cypher", "")
        query = state.get("mit_search_query", "")
        filters = state.get("mit_search_filters", {})
        user_id = state.get("user_id", "")

        if not cypher:
            logger.warning("No Cypher query to execute")
            return {"mit_search_raw_results": []}

        # 파라미터 준비
        parameters = {
            "query": query,
            "user_id": user_id
        }

        # 시간 필터 파라미터 추가
        date_range = filters.get("date_range")
        if date_range:
            parameters["start_date"] = date_range.get("start")
            parameters["end_date"] = date_range.get("end")

        # Cypher 실행 (비동기)
        results = await execute_cypher_search_async(
            cypher_query=cypher,
            parameters=parameters
        )

        logger.info(f"Retrieved {len(results)} raw results")

        return {"mit_search_raw_results": results}

    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return {"mit_search_raw_results": []}


def tool_executor(state: MitSearchState) -> dict:
    """동기 테스트용 래퍼."""
    return asyncio.run(tool_executor_async(state))
