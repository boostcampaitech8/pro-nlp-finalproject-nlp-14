"""MIT Search 서브그래프를 위한 Neo4j 검색 도구."""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def execute_cypher_search_async(cypher_query: str, parameters: dict[str, Any]) -> list[dict]:
    """
    Neo4j에 대해 파라미터와 함께 Cypher 쿼리 실행 (비동기).

    보안:
    - 위험한 작업에 대한 쿼리 검증
    - 파라미터화된 쿼리 사용
    - user_id 필터링 포함

    Args:
        cypher_query: 파라미터화된 Cypher 쿼리
        parameters: 쿼리 파라미터 (query, user_id 등)

    Returns:
        쿼리 결과 리스트
    """
    logger.info(f"Executing Cypher search with params: {list(parameters.keys())}")

    try:
        # Validate query safety
        dangerous_keywords = ["DROP", "DELETE", "DETACH", "CREATE", "MERGE", "SET", "REMOVE"]
        query_upper = cypher_query.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise ValueError(f"Dangerous Cypher keyword detected: {keyword}")

        # Neo4j driver integration
        from app.core.neo4j import get_neo4j_driver

        driver = get_neo4j_driver()

        async with driver.session() as session:
            result = await session.run(cypher_query, parameters)
            records = await result.data()

        logger.info(f"Cypher search returned {len(records)} results")
        return records

    except ValueError as ve:
        # 보안 에러는 로그 후 빈 결과 반환
        logger.error(f"Security validation failed: {ve}")
        return []
    except Exception as e:
        logger.error(f"Cypher search failed: {e}", exc_info=True)
        return []


def execute_cypher_search(cypher_query: str, parameters: dict[str, Any]) -> list[dict]:
    """
    Neo4j에 대해 파라미터와 함께 Cypher 쿼리 실행 (동기 래퍼).

    Args:
        cypher_query: 파라미터화된 Cypher 쿼리
        parameters: 쿼리 파라미터 (query, user_id 등)

    Returns:
        쿼리 결과 리스트
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 실행 중인 루프가 있으면 새 루프 생성
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, execute_cypher_search_async(cypher_query, parameters))
                return future.result(timeout=30)
        else:
            return asyncio.run(execute_cypher_search_async(cypher_query, parameters))
    except Exception as e:
        logger.error(f"Sync wrapper failed: {e}", exc_info=True)
        return []
