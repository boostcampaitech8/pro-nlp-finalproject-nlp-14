"""Redis 클라이언트 모듈

비동기 Redis 클라이언트 싱글톤 관리.
Egress 상태, 캐싱 등에 사용.
"""

import logging

import redis.asyncio as redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Redis 클라이언트 싱글톤 반환

    Returns:
        Redis 클라이언트 인스턴스
    """
    global _redis_client

    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info(f"[Redis] Connected to {settings.redis_url}")

    return _redis_client


async def close_redis() -> None:
    """Redis 연결 종료

    애플리케이션 종료 시 호출.
    """
    global _redis_client

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("[Redis] Connection closed")
