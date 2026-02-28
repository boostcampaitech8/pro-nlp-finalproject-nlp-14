"""Spotlight 세션 관리 서비스 (Redis 기반)"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.core.redis import get_redis
from app.infrastructure.graph.spotlight_checkpointer import get_spotlight_checkpointer

SESSION_TTL = 3600  # 1시간

logger = logging.getLogger(__name__)


@dataclass
class SpotlightSession:
    """Spotlight 세션 데이터"""

    session_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class SpotlightSessionService:
    """Spotlight 세션 관리"""

    _MAX_SESSIONS = 5

    @staticmethod
    def _session_key(user_id: str, session_id: str) -> str:
        return f"spotlight:session:{user_id}:{session_id}"

    @staticmethod
    def _sessions_zset_key(user_id: str) -> str:
        return f"spotlight:sessions:{user_id}"

    @staticmethod
    def _queue_key(user_id: str, session_id: str, kind: str) -> str:
        return f"spotlight:queue:{user_id}:{session_id}:{kind}"

    @staticmethod
    def _queue_lock_key(user_id: str, session_id: str) -> str:
        return f"spotlight:queue:lock:{user_id}:{session_id}"

    @staticmethod
    def _draft_key(user_id: str, session_id: str) -> str:
        return f"spotlight:draft:{user_id}:{session_id}"

    @staticmethod
    def _inflight_key(user_id: str, session_id: str) -> str:
        return f"spotlight:inflight:{user_id}:{session_id}"

    @staticmethod
    def _payload_key(request_id: str) -> str:
        return f"spotlight:queue:payload:{request_id}"

    async def _cleanup_session_resources(self, user_id: str, session_id: str) -> None:
        redis = await get_redis()
        session_key = self._session_key(user_id, session_id)
        zset_key = self._sessions_zset_key(user_id)

        # 큐에 남아 있는 요청 payload 정리
        normal_queue = self._queue_key(user_id, session_id, "normal")
        priority_queue = self._queue_key(user_id, session_id, "priority")
        pending_request_ids: list[str] = []
        pending_request_ids.extend(await redis.lrange(normal_queue, 0, -1))
        pending_request_ids.extend(await redis.lrange(priority_queue, 0, -1))
        if pending_request_ids:
            await redis.delete(*[self._payload_key(rid) for rid in pending_request_ids])

        # Redis 키 삭제
        await redis.delete(
            session_key,
            normal_queue,
            priority_queue,
            self._queue_lock_key(user_id, session_id),
            self._draft_key(user_id, session_id),
            self._inflight_key(user_id, session_id),
        )
        await redis.zrem(zset_key, session_id)

        # 체크포인터 삭제
        checkpointer = await get_spotlight_checkpointer()
        await checkpointer.adelete_thread(f"spotlight:{session_id}")

    async def create_session(self, user_id: str) -> SpotlightSession:
        """새 세션 생성"""
        redis = await get_redis()
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # 세션 수 제한 (최대 5개)
        zset_key = self._sessions_zset_key(user_id)
        count = await redis.zcard(zset_key)
        if count >= self._MAX_SESSIONS:
            over = count - (self._MAX_SESSIONS - 1)
            oldest_session_ids = await redis.zrange(zset_key, 0, over - 1)
            for old_session_id in oldest_session_ids:
                logger.info("세션 자동 삭제 (최대 제한): user=%s, session=%s", user_id, old_session_id)
                await self._cleanup_session_resources(user_id, old_session_id)

        session = SpotlightSession(
            session_id=session_id,
            user_id=user_id,
            title="새 대화",
            created_at=now,
            updated_at=now,
            message_count=0,
        )

        # Redis에 세션 저장
        key = self._session_key(user_id, session_id)
        data = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": session.message_count,
        }
        await redis.set(key, json.dumps(data), ex=SESSION_TTL)

        # ZSET에 추가 (최신순 정렬용)
        await redis.zadd(zset_key, {session_id: now.timestamp()})

        return session

    async def get_session(
        self, user_id: str, session_id: str
    ) -> Optional[SpotlightSession]:
        """세션 조회 (TTL 자동 갱신)"""
        redis = await get_redis()
        key = self._session_key(user_id, session_id)
        data = await redis.get(key)

        if not data:
            return None

        session_data = json.loads(data)

        # TTL 갱신
        await redis.expire(key, SESSION_TTL)

        return SpotlightSession(
            session_id=session_data["session_id"],
            user_id=session_data["user_id"],
            title=session_data["title"],
            created_at=datetime.fromisoformat(session_data["created_at"]),
            updated_at=datetime.fromisoformat(session_data["updated_at"]),
            message_count=session_data["message_count"],
        )

    async def list_sessions(self, user_id: str) -> list[SpotlightSession]:
        """세션 목록 조회 (최신순)"""
        redis = await get_redis()
        zset_key = self._sessions_zset_key(user_id)

        # 최신순으로 세션 ID 가져오기
        session_ids = await redis.zrevrange(zset_key, 0, -1)

        sessions = []
        expired_ids = []

        for session_id in session_ids:
            session = await self.get_session(user_id, session_id)
            if session:
                sessions.append(session)
            else:
                expired_ids.append(session_id)

        # 만료된 세션 ZSET에서 정리
        if expired_ids:
            await redis.zrem(zset_key, *expired_ids)

        return sessions

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """세션 삭제"""
        redis = await get_redis()
        key = self._session_key(user_id, session_id)
        exists = await redis.exists(key)
        await self._cleanup_session_resources(user_id, session_id)
        return exists > 0

    async def touch_session(self, user_id: str, session_id: str) -> bool:
        """TTL 갱신"""
        redis = await get_redis()
        key = self._session_key(user_id, session_id)
        return await redis.expire(key, SESSION_TTL)

    async def update_session(
        self,
        user_id: str,
        session_id: str,
        title: Optional[str] = None,
        increment_message_count: bool = False,
    ) -> Optional[SpotlightSession]:
        """세션 업데이트"""
        session = await self.get_session(user_id, session_id)
        if not session:
            return None

        redis = await get_redis()
        key = self._session_key(user_id, session_id)

        now = datetime.now(timezone.utc)
        if title:
            session.title = title
        if increment_message_count:
            session.message_count += 1
        session.updated_at = now

        data = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": session.message_count,
        }
        await redis.set(key, json.dumps(data), ex=SESSION_TTL)

        # ZSET 점수 업데이트
        zset_key = self._sessions_zset_key(user_id)
        await redis.zadd(zset_key, {session_id: now.timestamp()})

        return session
