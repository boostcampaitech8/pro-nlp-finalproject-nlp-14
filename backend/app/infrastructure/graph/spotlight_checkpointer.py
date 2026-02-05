"""Spotlight 전용 Redis Checkpointer"""

import asyncio
import base64
import json
import logging
import pickle
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# 모듈 레벨 싱글톤 (lazy initialization)
_checkpointer_redis: "RedisCheckpointSaver | None" = None
_lock = asyncio.Lock()

REDIS_CHECKPOINT_TTL = 3600
REDIS_PREFIX = "spotlight:checkpoint"


class RedisCheckpointSaver(BaseCheckpointSaver[str]):
    """Redis 기반 Checkpointer (Spotlight 전용)."""

    def __init__(self, *, ttl: int = REDIS_CHECKPOINT_TTL) -> None:
        super().__init__()
        self.ttl = ttl

    def _key_latest(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{REDIS_PREFIX}:latest:{thread_id}:{checkpoint_ns}"

    def _key_checkpoint(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{REDIS_PREFIX}:data:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    def _key_index(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{REDIS_PREFIX}:index:{thread_id}:{checkpoint_ns}"

    def _key_writes(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{REDIS_PREFIX}:writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    def _pack(self, obj: Any) -> str:
        typed = self.serde.dumps_typed(obj)
        raw = pickle.dumps(typed)
        return base64.b64encode(raw).decode("ascii")

    def _unpack(self, data: str) -> Any:
        raw = base64.b64decode(data.encode("ascii"))
        typed = pickle.loads(raw)
        return self.serde.loads_typed(typed)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)
        redis = await get_redis()

        if not checkpoint_id:
            checkpoint_id = await redis.get(self._key_latest(thread_id, checkpoint_ns))
            if not checkpoint_id:
                return None

        payload = await redis.get(self._key_checkpoint(thread_id, checkpoint_ns, checkpoint_id))
        if not payload:
            return None

        record = json.loads(payload)
        checkpoint = self._unpack(record["checkpoint"])
        metadata = self._unpack(record["metadata"])
        parent_checkpoint_id = record.get("parent_checkpoint_id")

        writes_key = self._key_writes(thread_id, checkpoint_ns, checkpoint_id)
        writes_values = await redis.hvals(writes_key)
        pending_writes = []
        for raw in writes_values:
            write_record = json.loads(raw)
            pending_writes.append(
                (
                    write_record["task_id"],
                    write_record["channel"],
                    self._unpack(write_record["value"]),
                )
            )

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            ),
            pending_writes=pending_writes,
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if not config:
            return
        checkpoint = await self.aget_tuple(config)
        if checkpoint:
            yield checkpoint

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        redis = await get_redis()

        record = {
            "checkpoint": self._pack(checkpoint),
            "metadata": self._pack(get_checkpoint_metadata(config, metadata)),
            "parent_checkpoint_id": parent_checkpoint_id,
        }
        key_checkpoint = self._key_checkpoint(thread_id, checkpoint_ns, checkpoint["id"])
        await redis.set(key_checkpoint, json.dumps(record), ex=self.ttl)
        await redis.set(self._key_latest(thread_id, checkpoint_ns), checkpoint["id"], ex=self.ttl)
        await redis.zadd(self._key_index(thread_id, checkpoint_ns), {checkpoint["id"]: time.time()})
        await redis.expire(self._key_index(thread_id, checkpoint_ns), self.ttl)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]
        redis = await get_redis()

        writes_key = self._key_writes(thread_id, checkpoint_ns, checkpoint_id)
        for idx, (c, v) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(c, idx)
            field = f"{task_id}:{write_idx}"
            if write_idx >= 0:
                exists = await redis.hexists(writes_key, field)
                if exists:
                    continue
            record = {
                "task_id": task_id,
                "channel": c,
                "value": self._pack(v),
                "task_path": task_path,
            }
            await redis.hset(writes_key, field, json.dumps(record))
        await redis.expire(writes_key, self.ttl)

    async def adelete_thread(self, thread_id: str) -> None:
        redis = await get_redis()
        pattern = f"{REDIS_PREFIX}:*:{thread_id}:*"
        cursor = 0
        keys_to_delete: list[str] = []
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            keys_to_delete.extend(keys)
            if cursor == 0:
                break
        if keys_to_delete:
            await redis.delete(*keys_to_delete)


async def get_spotlight_checkpointer() -> RedisCheckpointSaver:
    """Spotlight 전용 Redis checkpointer 싱글톤 반환"""
    global _checkpointer_redis

    if _checkpointer_redis is None:
        async with _lock:
            if _checkpointer_redis is None:
                _checkpointer_redis = RedisCheckpointSaver()
                logger.info("Spotlight checkpointer is running with Redis (persistent)")
    return _checkpointer_redis


async def close_spotlight_checkpointer() -> None:
    """Spotlight checkpointer 정리"""
    global _checkpointer_redis
    if _checkpointer_redis is not None:
        _checkpointer_redis = None
        logger.info("Spotlight Redis checkpointer cleared")
