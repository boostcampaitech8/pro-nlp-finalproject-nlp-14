"""Spotlight 세션 관리 서비스 (Redis 기반)"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.core.redis import get_redis

SESSION_TTL = 3600  # 1시간


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

    @staticmethod
    def _session_key(user_id: str, session_id: str) -> str:
        return f"spotlight:session:{user_id}:{session_id}"

    @staticmethod
    def _sessions_zset_key(user_id: str) -> str:
        return f"spotlight:sessions:{user_id}"

    async def create_session(self, user_id: str) -> SpotlightSession:
        """새 세션 생성"""
        redis = await get_redis()
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

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
        zset_key = self._sessions_zset_key(user_id)
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
        zset_key = self._sessions_zset_key(user_id)

        deleted = await redis.delete(key)
        await redis.zrem(zset_key, session_id)

        return deleted > 0

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
