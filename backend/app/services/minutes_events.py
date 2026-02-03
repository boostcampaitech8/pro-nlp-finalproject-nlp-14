"""Minutes 실시간 이벤트 관리자

회의록 변경 이벤트를 구독자들에게 브로드캐스트합니다.
Redis Pub/Sub 기반 - 프로세스 간 통신 지원 (API 서버 ↔ ARQ Worker).
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class MinutesEventManager:
    """Minutes 이벤트 Pub/Sub 관리자 (Redis 기반)

    Redis Pub/Sub을 사용하여 프로세스 간 이벤트 전달을 지원합니다.
    - API 서버에서 publish → 모든 API 서버의 SSE 구독자에게 전달
    - ARQ Worker에서 publish → 모든 API 서버의 SSE 구독자에게 전달
    """

    def __init__(self):
        self._publish_redis: Redis | None = None

    async def _get_publish_redis(self) -> Redis:
        """Publish용 Redis 연결 (lazy initialization)"""
        if self._publish_redis is None:
            settings = get_settings()
            self._publish_redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5.0,
            )
        return self._publish_redis

    async def publish(self, meeting_id: str, event: dict) -> None:
        """이벤트 발행 (Redis Pub/Sub)

        해당 회의 채널에 이벤트를 발행합니다.
        모든 프로세스의 구독자가 수신합니다.

        Args:
            meeting_id: 회의 ID
            event: 이벤트 데이터 {"event": "...", ...}
        """
        try:
            redis = await self._get_publish_redis()
            channel = f"minutes:{meeting_id}"
            await redis.publish(channel, json.dumps(event))
            logger.debug(f"Published event to {channel}: {event.get('event')}")
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

    async def subscribe(self, meeting_id: str) -> AsyncGenerator[dict, None]:
        """이벤트 구독 (Redis Pub/Sub)

        SSE 엔드포인트에서 사용하는 async generator.
        Redis Pub/Sub 채널을 구독하여 이벤트를 수신합니다.

        Args:
            meeting_id: 구독할 회의 ID

        Yields:
            이벤트 dict
        """
        settings = get_settings()
        # Subscribe용 별도 Redis 연결 (pubsub은 연결을 점유함)
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5.0,
        )
        pubsub = redis.pubsub()
        channel = f"minutes:{meeting_id}"

        try:
            await pubsub.subscribe(channel)
            logger.info(f"SSE subscriber connected: channel={channel}")

            # listen()을 사용한 async iteration
            last_event_time = asyncio.get_event_loop().time()

            async for message in pubsub.listen():
                # subscribe 확인 메시지 무시
                if message["type"] == "subscribe":
                    continue

                if message["type"] == "message":
                    try:
                        event = json.loads(message["data"])
                        last_event_time = asyncio.get_event_loop().time()
                        yield event
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid event JSON: {e}")

                # 30초마다 keepalive 체크 (listen은 블로킹이므로 별도 태스크 필요)
                current_time = asyncio.get_event_loop().time()
                if current_time - last_event_time > 30:
                    last_event_time = current_time
                    yield {"event": "keepalive"}

        except asyncio.CancelledError:
            logger.info(f"SSE subscription cancelled: channel={channel}")
            raise
        except Exception as e:
            logger.error(f"SSE subscription error: {e}")
            raise
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis.close()
            logger.info(f"SSE subscriber disconnected: channel={channel}")


# 싱글톤 인스턴스 (애플리케이션 전역)
minutes_event_manager = MinutesEventManager()
