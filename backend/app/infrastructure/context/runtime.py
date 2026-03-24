"""Runtime cache utilities for context retrieval.

2-Step RAG에서 토픽 단위 원문 발화 캐싱을 담당한다.
"""

from __future__ import annotations

import json
import logging

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class TopicUtteranceCache:
    """회의/토픽 단위 원문 발화 캐시.

    Key format:
        {meeting_id}:topic:{topic_id}:utterances
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _build_key(meeting_id: str, topic_id: str) -> str:
        return f"{meeting_id}:topic:{topic_id}:utterances"

    async def get(self, meeting_id: str, topic_id: str) -> list[dict] | None:
        """캐시된 발화 조회.

        Returns:
            list[dict] | None: hit 시 발화 리스트, miss 시 None
        """
        key = self._build_key(meeting_id, topic_id)
        try:
            redis = await get_redis()
            payload = await redis.get(key)
            if not payload:
                return None
            value = json.loads(payload)
            if isinstance(value, list):
                return value
            return None
        except Exception as e:
            logger.debug("TopicUtteranceCache.get failed (non-critical): %s", e)
            return None

    async def set(self, meeting_id: str, topic_id: str, utterances: list[dict]) -> None:
        """토픽 발화 목록 캐시 저장."""
        key = self._build_key(meeting_id, topic_id)
        try:
            redis = await get_redis()
            payload = json.dumps(utterances, ensure_ascii=True)
            await redis.setex(key, self.ttl_seconds, payload)
        except Exception as e:
            logger.debug("TopicUtteranceCache.set failed (non-critical): %s", e)

