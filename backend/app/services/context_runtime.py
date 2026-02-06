"""ContextManager runtime cache for real-time updates.

TTL Cache를 사용하여 메모리 누수 방지:
- 최대 10개 회의 동시 캐시
- 1시간 미접근 시 자동 삭제
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.context import ContextConfig, ContextManager, Utterance
from app.models.transcript import Transcript

logger = logging.getLogger(__name__)


@dataclass
class ContextRuntimeState:
    manager: ContextManager
    lock: asyncio.Lock
    last_processed_start_ms: int | None = None
    last_utterance_id: int = 0
    topic_publish_task: asyncio.Task | None = None


# TTL Cache: 동시 최대 10개 회의, 1시간 미접근 시 자동 삭제
_runtime_cache: TTLCache[str, ContextRuntimeState] = TTLCache(
    maxsize=10,
    ttl=3600,  # 1시간
)
_runtime_lock = asyncio.Lock()


async def get_or_create_runtime(
    meeting_id: str, mode: str = "voice"
) -> ContextRuntimeState:
    async with _runtime_lock:
        runtime = _runtime_cache.get(meeting_id)
        if runtime is None:
            runtime = ContextRuntimeState(
                manager=ContextManager(
                    meeting_id=meeting_id, config=ContextConfig(), mode=mode
                ),
                lock=asyncio.Lock(),
            )
            _runtime_cache[meeting_id] = runtime
        return runtime


def get_runtime_if_exists(meeting_id: str) -> ContextRuntimeState | None:
    return _runtime_cache.get(meeting_id)


async def get_transcript_start_ms(
    db: AsyncSession,
    transcript_id: UUID,
) -> int | None:
    result = await db.execute(
        select(Transcript.start_ms).where(Transcript.id == transcript_id)
    )
    return result.scalar_one_or_none()


async def get_latest_start_ms(db: AsyncSession, meeting_id: str) -> int | None:
    result = await db.execute(
        select(Transcript.start_ms)
        .where(Transcript.meeting_id == UUID(meeting_id))
        .order_by(Transcript.start_ms.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_runtime_from_db(
    runtime: ContextRuntimeState,
    db: AsyncSession,
    meeting_id: str,
    cutoff_start_ms: int | None,
) -> int:
    query = select(Transcript).where(Transcript.meeting_id == UUID(meeting_id))

    if runtime.last_processed_start_ms is not None:
        query = query.where(Transcript.start_ms > runtime.last_processed_start_ms)

    if cutoff_start_ms is not None:
        query = query.where(Transcript.start_ms <= cutoff_start_ms)

    query = query.order_by(Transcript.start_ms)

    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return 0

    for row in rows:
        runtime.last_utterance_id += 1
        utterance = Utterance(
            id=runtime.last_utterance_id,
            speaker_id=str(row.user_id),
            speaker_name="",  # TODO: user 테이블 조인으로 이름 가져오기
            text=row.transcript_text,
            start_ms=row.start_ms,
            end_ms=row.end_ms,
            confidence=row.confidence,
            absolute_timestamp=row.start_at or row.created_at or datetime.now(timezone.utc),
        )
        await runtime.manager.add_utterance(utterance)
        runtime.last_processed_start_ms = row.start_ms

    logger.info(
        "Context runtime updated: meeting_id=%s, added=%d, last_start_ms=%s",
        meeting_id,
        len(rows),
        runtime.last_processed_start_ms,
    )
    return len(rows)
