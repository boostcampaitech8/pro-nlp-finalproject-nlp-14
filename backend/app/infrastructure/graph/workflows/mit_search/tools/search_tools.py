"""MIT Search 서브그래프를 위한 Neo4j 검색 도구."""

import asyncio
import logging
from typing import Any

from neo4j import READ_ACCESS

logger = logging.getLogger(__name__)


def _serialize_neo4j_types(data):
    """Neo4j 특수 타입(DateTime, Date 등)을 Python 기본 타입으로 변환.

    LangGraph의 msgpack 직렬화와 호환되도록 Neo4j 객체를 변환합니다.

    Args:
        data: Neo4j 쿼리 결과 (dict, list, DateTime 등)

    Returns:
        직렬화 가능한 Python 기본 타입
    """
    from neo4j.time import DateTime, Date, Time

    if isinstance(data, (DateTime, Date, Time)):
        # Neo4j DateTime/Date/Time을 ISO 형식 문자열로 변환
        return data.isoformat()
    elif isinstance(data, dict):
        return {key: _serialize_neo4j_types(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_serialize_neo4j_types(item) for item in data]
    else:
        return data


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
    print(f"\n[DEBUG] 전체 파라미터: {parameters}")
    print(f"[DEBUG] entity_name 값: '{parameters.get('entity_name')}'")
    print(f"[DEBUG] user_id 값: '{parameters.get('user_id')}'")

    try:
        # Validate query safety - 단어 경계를 포함하여 검사
        dangerous_keywords = ["DROP", "DELETE", "DETACH", "CREATE", "MERGE", "SET", "REMOVE"]
        query_upper = cypher_query.upper()
        
        import re
        for keyword in dangerous_keywords:
            # 단어 경계를 포함하여 정확히 검사 (created_at 같은 컬럼명은 통과)
            if re.search(rf'\b{keyword}\b', query_upper):
                raise ValueError(f"Dangerous Cypher keyword detected: {keyword}")

        # Neo4j driver integration
        from app.core.neo4j import get_neo4j_driver

        driver = get_neo4j_driver()

        print(f"[DEBUG] Neo4j 실행 직전 - 쿼리 길이: {len(cypher_query)}, 파라미터 키: {list(parameters.keys())}")
        print(f"[DEBUG] Neo4j 실행 직전 - 파라미터 타입 확인:")
        for key, value in parameters.items():
            print(f"  - {key}: {type(value).__name__} = {repr(value)}")

        async with driver.session(default_access_mode=READ_ACCESS) as session:
            print(f"[DEBUG] session.run() 호출 중...")
            try:
                result = await session.run(cypher_query, parameters)
                print(f"[DEBUG] session.run() 성공")
                records = await result.data()
                print(f"[DEBUG] result.data() 완료: {len(records)}개 레코드")
            except Exception as neo_error:
                print(f"\n[NEO4J ERROR] 타입: {type(neo_error).__name__}")
                print(f"[NEO4J ERROR] 메시지: {neo_error}")
                print(f"[NEO4J ERROR] 실행 시도한 쿼리:\n{cypher_query}")
                print(f"[NEO4J ERROR] 전달한 파라미터: {parameters}")
                raise

        logger.info(f"Cypher search returned {len(records)} results")
        # Neo4j DateTime 객체를 ISO 문자열로 변환하여 msgpack 직렬화 가능하도록 처리
        return [_serialize_neo4j_types(record) for record in records]

    except ValueError as ve:
        # 보안 에러는 로그 후 빈 결과 반환
        logger.error(f"Security validation failed: {ve}")
        return []
    except Exception as e:
        logger.error(f"Cypher search failed: {e}", exc_info=True)
        print(f"\n[ERROR] Cypher 실행 실패: {type(e).__name__}: {e}")
        print(f"[ERROR] 사용된 파라미터: {parameters}")
        print(f"[ERROR] 사용된 쿼리:\n{cypher_query}")
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
