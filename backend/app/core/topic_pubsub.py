"""토픽 변경 알림을 위한 Redis Pub/Sub 모듈

SSE 스트리밍을 위해 토픽 변경 이벤트를 Redis로 발행/구독합니다.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# Redis 채널 이름 패턴
TOPIC_CHANNEL_PREFIX = "meeting:topics:"


def get_topic_channel(meeting_id: str) -> str:
    """회의별 토픽 채널 이름 생성"""
    return f"{TOPIC_CHANNEL_PREFIX}{meeting_id}"


async def publish_topic_update(meeting_id: str, data: dict) -> None:
    """토픽 변경 이벤트 발행

    Args:
        meeting_id: 회의 ID
        data: 발행할 토픽 데이터 (TopicFeedResponse 형태)
    """
    try:
        redis = await get_redis()
        channel = get_topic_channel(meeting_id)
        message = json.dumps(data, ensure_ascii=False, default=str)
        await redis.publish(channel, message)
        logger.debug("토픽 업데이트 발행: channel=%s", channel)
    except Exception as e:
        logger.warning("토픽 발행 실패 (비치명적): %s", e)


async def subscribe_topic_updates(meeting_id: str) -> AsyncGenerator[dict, None]:
    """토픽 변경 이벤트 구독 (SSE용 제너레이터)

    Args:
        meeting_id: 회의 ID

    Yields:
        토픽 데이터 dict
    """
    redis = await get_redis()
    channel = get_topic_channel(meeting_id)
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(channel)
        logger.info("토픽 구독 시작: channel=%s", channel)

        while True:
            try:
                # get_message(timeout=1.0): 최대 1초 대기 후 메시지 없으면 None 반환
                # wait_for(timeout=30.0): Redis 연결이 응답하지 않을 경우 안전장치
                #
                # 동작 흐름:
                # 1. 메시지 있음 → 즉시 반환 → update 이벤트 전송
                # 2. 메시지 없음 → 1초 후 None 반환 → heartbeat 전송 → 루프 반복
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=30.0,
                )

                if message is None:
                    # Heartbeat (keep-alive)
                    yield {"type": "heartbeat"}
                    continue

                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield {"type": "update", "data": data}

            except asyncio.TimeoutError:
                # 30초 heartbeat
                yield {"type": "heartbeat"}

    except asyncio.CancelledError:
        logger.info("토픽 구독 취소: channel=%s", channel)
        raise
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        logger.info("토픽 구독 종료: channel=%s", channel)
