"""Clova STT API Key Manager

Redis 기반 동적 API 키 할당 관리.
ZSET으로 회의-키 할당 상태를 관리하여 TTL 만료 누수를 방지.
Lua 스크립트로 원자적 할당/반환을 보장하여 race condition 방지.
Redis Cluster 대응을 위해 해시태그 키 스키마 사용.
"""

import logging

from redis.asyncio import Redis

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# Redis Cluster 대응을 위한 해시태그
HASH_TAG = "clova_stt"
KEY_PREFIX = f"clova:{{{HASH_TAG}}}"

# Lua 스크립트: 키 할당 (Least Connections 알고리즘)
ALLOCATE_SCRIPT = """
-- ALLOCATE_SCRIPT
-- KEYS: [1] = meeting_key
-- ARGV: [1] = total_keys, [2] = max_meetings_per_key, [3] = ttl_seconds, [4] = key_prefix

local meeting_key = KEYS[1]
local total_keys = tonumber(ARGV[1])
local max_meetings = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local key_prefix = ARGV[4]

-- 1. 이미 할당된 키 확인 (멱등성)
local existing = redis.call('GET', meeting_key)
if existing then
    return tonumber(existing)
end

-- 2. 현재 시간 (seconds)
local now = redis.call('TIME')
local now_sec = tonumber(now[1])

-- 3. TTL 만료 정리
for i = 0, total_keys - 1 do
    local zkey = key_prefix .. ':key:' .. i .. ':meetings'
    redis.call('ZREMRANGEBYSCORE', zkey, '-inf', now_sec)
end

-- 4. Least Connections: 가장 여유 있는 키 찾기
local best_key = nil
local min_count = max_meetings

for i = 0, total_keys - 1 do
    local zkey = key_prefix .. ':key:' .. i .. ':meetings'
    local count = tonumber(redis.call('ZCARD', zkey))

    if count < min_count then
        min_count = count
        best_key = i

        -- 빈 키 발견 시 즉시 선택
        if count == 0 then
            break
        end
    end
end

-- 5. 사용 가능한 키 없음
if best_key == nil then
    return nil
end

-- 6. 원자적 할당
local expire_at = now_sec + ttl
local best_zkey = key_prefix .. ':key:' .. best_key .. ':meetings'
redis.call('ZADD', best_zkey, expire_at, meeting_key)
redis.call('SET', meeting_key, best_key, 'EX', ttl)

return best_key
"""

# Lua 스크립트: 키 반환
RELEASE_SCRIPT = """
-- RELEASE_SCRIPT
-- KEYS: [1] = meeting_key
-- ARGV: [1] = total_keys, [2] = key_prefix

local meeting_key = KEYS[1]
local total_keys = tonumber(ARGV[1])
local key_prefix = ARGV[2]

-- 1. 현재 시간 (seconds)
local now = redis.call('TIME')
local now_sec = tonumber(now[1])

-- 2. 할당된 키 확인
local key_index = redis.call('GET', meeting_key)

if key_index then
    local zkey = key_prefix .. ':key:' .. key_index .. ':meetings'
    redis.call('ZREM', zkey, meeting_key)
    redis.call('DEL', meeting_key)
else
    -- meeting_key가 없는 경우에도 모든 키에서 제거 시도 (중복/TTL 만료 대응)
    for i = 0, total_keys - 1 do
        local zkey = key_prefix .. ':key:' .. i .. ':meetings'
        redis.call('ZREM', zkey, meeting_key)
    end
end

-- 3. TTL 만료 정리
for i = 0, total_keys - 1 do
    local zkey = key_prefix .. ':key:' .. i .. ':meetings'
    redis.call('ZREMRANGEBYSCORE', zkey, '-inf', now_sec)
end

if key_index then
    return 1
end
return 0
"""


class ClovaKeyManager:
    """Redis 기반 Clova STT API 키 할당 관리자

    Least Connections 알고리즘으로 가장 여유 있는 키를 할당합니다.
    Lua 스크립트로 원자적 연산을 보장합니다.
    """

    # 회의당 평균 7명 가정
    MAX_MEETINGS_PER_KEY = 2
    # 4시간 TTL (좀비 키 자동 정리)
    MEETING_KEY_TTL = 4 * 60 * 60

    def __init__(self, redis: Redis, total_keys: int = 5):
        """
        Args:
            redis: Redis 클라이언트 인스턴스
            total_keys: 사용 가능한 API 키 총 개수
        """
        self.redis = redis
        self.total_keys = total_keys
        self.max_meetings_per_key = self.MAX_MEETINGS_PER_KEY
        self.meeting_key_ttl = self.MEETING_KEY_TTL
        self.key_prefix = KEY_PREFIX

        # Lua 스크립트 등록
        self._allocate_script = self.redis.register_script(ALLOCATE_SCRIPT)
        self._release_script = self.redis.register_script(RELEASE_SCRIPT)

    def _meeting_key(self, meeting_id: str) -> str:
        return f"{self.key_prefix}:meeting:{meeting_id}"

    def _key_zset(self, key_index: int) -> str:
        return f"{self.key_prefix}:key:{key_index}:meetings"

    async def allocate_key(self, meeting_id: str) -> int | None:
        """회의에 API 키 할당

        Least Connections 알고리즘으로 가장 여유 있는 키를 선택합니다.
        Lua 스크립트로 원자적 할당을 보장합니다.

        Args:
            meeting_id: 회의 ID

        Returns:
            할당된 키 인덱스 (0-4) 또는 None (사용 가능한 키 없음)
        """
        meeting_key = self._meeting_key(meeting_id)

        result = await self._allocate_script(
            keys=[meeting_key],
            args=[
                self.total_keys,
                self.max_meetings_per_key,
                self.meeting_key_ttl,
                self.key_prefix,
            ],
        )

        if result is None:
            logger.warning(f"사용 가능한 API 키 없음: meeting={meeting_id}")
            return None

        key_index = int(result)
        logger.info(f"API 키 할당: meeting={meeting_id}, key_index={key_index}")
        return key_index

    async def release_key(self, meeting_id: str) -> bool:
        """회의의 API 키 반환

        Args:
            meeting_id: 회의 ID

        Returns:
            반환 성공 여부
        """
        meeting_key = self._meeting_key(meeting_id)

        result = await self._release_script(
            keys=[meeting_key],
            args=[
                self.total_keys,
                self.key_prefix,
            ],
        )

        released = bool(result)
        if released:
            logger.info(f"API 키 반환: meeting={meeting_id}")
        else:
            logger.debug(f"반환할 키 없음 (이미 반환됨): meeting={meeting_id}")

        return released

    async def get_key_index(self, meeting_id: str) -> int | None:
        """회의에 할당된 키 인덱스 조회

        Args:
            meeting_id: 회의 ID

        Returns:
            할당된 키 인덱스 또는 None
        """
        meeting_key = self._meeting_key(meeting_id)
        result = await self.redis.get(meeting_key)
        return int(result) if result else None

    async def get_status(self) -> dict:
        """전체 키 사용 현황 조회

        Returns:
            키별 사용 현황 딕셔너리
        """
        # TTL 만료된 항목을 먼저 정리
        now = await self.redis.time()
        now_sec = now[0]

        async with self.redis.pipeline() as pipe:
            # 1. 먼저 만료된 항목 정리
            for i in range(self.total_keys):
                pipe.zremrangebyscore(self._key_zset(i), "-inf", now_sec)
            await pipe.execute()

        status = {}

        # 2. Pipeline으로 일괄 조회
        async with self.redis.pipeline() as pipe:
            for i in range(self.total_keys):
                pipe.zcard(self._key_zset(i))
            results = await pipe.execute()

        for i, count_str in enumerate(results):
            meetings = int(count_str) if count_str else 0
            status[i] = {
                "meetings": meetings,
                "available": self.max_meetings_per_key - meetings,
            }

        return status


# 싱글톤 인스턴스
_key_manager: ClovaKeyManager | None = None


async def get_clova_key_manager() -> ClovaKeyManager:
    """ClovaKeyManager 싱글톤 반환 (비동기)

    get_redis()가 비동기이므로 이 함수도 비동기입니다.
    """
    global _key_manager
    if _key_manager is None:
        from app.core.config import get_settings

        redis = await get_redis()
        settings = get_settings()
        _key_manager = ClovaKeyManager(
            redis=redis,
            total_keys=getattr(settings, "clova_stt_key_count", 5),
        )
    return _key_manager
