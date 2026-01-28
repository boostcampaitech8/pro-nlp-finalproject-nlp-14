"""Neo4j 드라이버 모듈

비동기 Neo4j 드라이버 싱글턴 관리.
Knowledge Graph 저장소에 사용.
"""

import logging
from functools import lru_cache

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_neo4j_driver() -> AsyncDriver:
    """Neo4j 드라이버 싱글턴 반환

    Returns:
        Neo4j AsyncDriver 인스턴스
    """
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        # 원격 DB 연결 안정화 설정 (VPN 환경 최적화)
        max_connection_lifetime=300,   # 연결 수명 5분 (VPN idle timeout 대응)
        max_connection_pool_size=10,   # 최대 연결 풀 크기 (로컬 개발 환경)
        connection_acquisition_timeout=30.0,  # 연결 획득 타임아웃 30초
        connection_timeout=30.0,       # 연결 타임아웃 30초
    )
    logger.info(f"[Neo4j] Driver created for {settings.neo4j_uri}")
    return driver


async def close_neo4j() -> None:
    """Neo4j 연결 종료

    애플리케이션 종료 시 호출.
    """
    try:
        driver = get_neo4j_driver()
        await driver.close()
        get_neo4j_driver.cache_clear()
        logger.info("[Neo4j] Connection closed")
    except Exception:
        # 드라이버가 생성되지 않은 경우
        pass
