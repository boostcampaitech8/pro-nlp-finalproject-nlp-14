"""Clova Key Manager 단위 테스트 (Redis 기반)

테스트 케이스:
- 키 할당: 성공, Least Connections, 멱등성, 소진
- 키 반환: 성공, 없는 키, 반환 후 재사용
- 상태 조회
"""

from unittest.mock import AsyncMock

import pytest

from app.services.clova_key_manager import ClovaKeyManager


class MockRedisForClovaKeyManager:
    """ClovaKeyManager 테스트용 Redis Mock

    Lua 스크립트 로직을 Python으로 시뮬레이션합니다.
    """

    def __init__(self):
        self._strings: dict[str, str] = {}
        self._expires: dict[str, int] = {}
        self._zsets: dict[str, dict[str, int]] = {}
        self._now: int = 0

    def advance_time(self, seconds: int) -> None:
        self._now += seconds

    async def time(self) -> tuple[int, int]:
        """Redis TIME 명령어 Mock - (seconds, microseconds) 반환"""
        return (self._now, 0)

    def register_script(self, script: str):
        """Lua 스크립트 등록 - 실제 로직을 Python으로 구현"""
        if "-- ALLOCATE_SCRIPT" in script:
            return self._create_allocate_mock()
        if "-- RELEASE_SCRIPT" in script:
            return self._create_release_mock()
        raise ValueError("Unknown Lua script")

    def _get_string(self, key: str) -> str | None:
        expire_at = self._expires.get(key)
        if expire_at is not None and expire_at <= self._now:
            self._strings.pop(key, None)
            self._expires.pop(key, None)
            return None
        return self._strings.get(key)

    def _set_string(self, key: str, value: str, ttl: int) -> None:
        self._strings[key] = value
        self._expires[key] = self._now + ttl

    def _del_string(self, key: str) -> None:
        self._strings.pop(key, None)
        self._expires.pop(key, None)

    def _zadd(self, key: str, member: str, score: int) -> None:
        zset = self._zsets.setdefault(key, {})
        zset[member] = score

    def _zrem(self, key: str, member: str) -> None:
        zset = self._zsets.get(key)
        if zset is not None:
            zset.pop(member, None)

    def _zremrangebyscore(self, key: str, min_score: float, max_score: float) -> None:
        zset = self._zsets.get(key)
        if not zset:
            return
        to_remove = [member for member, score in zset.items() if min_score <= score <= max_score]
        for member in to_remove:
            zset.pop(member, None)

    def _zcard(self, key: str) -> int:
        zset = self._zsets.get(key)
        return len(zset) if zset else 0

    def _create_allocate_mock(self):
        """allocate_key Lua 스크립트 시뮬레이션"""

        async def allocate(keys: list, args: list):
            meeting_key = keys[0]
            total_keys = int(args[0])
            max_meetings = int(args[1])
            ttl = int(args[2])
            key_prefix = args[3]

            # 1. 이미 할당된 키 확인 (멱등성)
            existing = self._get_string(meeting_key)
            if existing is not None:
                return int(existing)

            now = self._now

            # 2. TTL 만료 정리
            for i in range(total_keys):
                zkey = f"{key_prefix}:key:{i}:meetings"
                self._zremrangebyscore(zkey, float("-inf"), now)

            # 3. Least Connections: 가장 여유 있는 키 찾기
            best_key = None
            min_count = max_meetings

            for i in range(total_keys):
                zkey = f"{key_prefix}:key:{i}:meetings"
                count = self._zcard(zkey)

                if count < min_count:
                    min_count = count
                    best_key = i
                    if count == 0:
                        break

            if best_key is None:
                return None

            expire_at = now + ttl
            best_zkey = f"{key_prefix}:key:{best_key}:meetings"
            self._zadd(best_zkey, meeting_key, expire_at)
            self._set_string(meeting_key, str(best_key), ttl)

            return best_key

        return allocate

    def _create_release_mock(self):
        """release_key Lua 스크립트 시뮬레이션"""

        async def release(keys: list, args: list):
            meeting_key = keys[0]
            total_keys = int(args[0])
            key_prefix = args[1]

            now = self._now

            key_index = self._get_string(meeting_key)
            if key_index is not None:
                zkey = f"{key_prefix}:key:{key_index}:meetings"
                self._zrem(zkey, meeting_key)
                self._del_string(meeting_key)
                existed = True
            else:
                existed = False
                for i in range(total_keys):
                    zkey = f"{key_prefix}:key:{i}:meetings"
                    self._zrem(zkey, meeting_key)

            for i in range(total_keys):
                zkey = f"{key_prefix}:key:{i}:meetings"
                self._zremrangebyscore(zkey, float("-inf"), now)

            return 1 if existed else 0

        return release

    async def get(self, key: str) -> str | None:
        """Redis GET"""
        return self._get_string(key)

    def pipeline(self):
        """Redis Pipeline Mock"""
        return MockPipeline(self)


class MockPipeline:
    """Redis Pipeline Mock"""

    def __init__(self, redis: MockRedisForClovaKeyManager):
        self._redis = redis
        self._commands: list[tuple[str, str | tuple]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def zcard(self, key: str):
        self._commands.append(("zcard", key))

    def zremrangebyscore(self, key: str, min_score: str | float, max_score: str | float):
        min_val = float("-inf") if min_score == "-inf" else float(min_score)
        max_val = float("+inf") if max_score == "+inf" else float(max_score)
        self._commands.append(("zremrangebyscore", (key, min_val, max_val)))

    async def execute(self) -> list:
        results = []
        for cmd, *args in self._commands:
            if cmd == "zcard":
                key = args[0]
                results.append(self._redis._zcard(key))
            elif cmd == "zremrangebyscore":
                key, min_score, max_score = args[0]
                self._redis._zremrangebyscore(key, min_score, max_score)
                results.append(None)  # zremrangebyscore는 삭제된 개수를 반환하지만 여기서는 무시
        return results


class TestClovaKeyManager:
    """ClovaKeyManager 단위 테스트 (Redis Mock)"""

    @pytest.fixture
    def mock_redis(self):
        """Redis Mock"""
        return MockRedisForClovaKeyManager()

    @pytest.fixture
    def manager(self, mock_redis):
        """테스트용 매니저 (3개 키, 키당 2회의 - MAX_MEETINGS_PER_KEY=2 고정)"""
        return ClovaKeyManager(redis=mock_redis, total_keys=3)

    # ===== 키 할당 테스트 =====

    @pytest.mark.asyncio
    async def test_allocate_key_success(self, manager):
        """첫 번째 할당은 인덱스 0 반환"""
        key_index = await manager.allocate_key("meeting-1")
        assert key_index == 0

    @pytest.mark.asyncio
    async def test_allocate_key_least_connections(self, manager):
        """Least Connections: 가장 여유 있는 키 선택"""
        # 각 키에 1개씩 할당
        key0 = await manager.allocate_key("meeting-1")  # key 0
        key1 = await manager.allocate_key("meeting-2")  # key 1
        key2 = await manager.allocate_key("meeting-3")  # key 2

        assert key0 == 0
        assert key1 == 1
        assert key2 == 2

        # 모든 키가 1개씩 사용 중 → 다시 0부터
        key_index = await manager.allocate_key("meeting-4")
        assert key_index == 0

    @pytest.mark.asyncio
    async def test_allocate_key_idempotent(self, manager):
        """같은 meeting_id는 같은 키 반환 (멱등성)"""
        key1 = await manager.allocate_key("meeting-1")
        key2 = await manager.allocate_key("meeting-1")
        assert key1 == key2

        # 사용량도 1번만 증가해야 함
        status = await manager.get_status()
        assert status[0]["meetings"] == 1

    @pytest.mark.asyncio
    async def test_allocate_key_exhausted(self, manager):
        """모든 키 소진 시 None 반환"""
        # 3개 키 × 2회의 = 6개 회의 가능
        for i in range(6):
            result = await manager.allocate_key(f"meeting-{i}")
            assert result is not None

        # 7번째는 None
        result = await manager.allocate_key("meeting-overflow")
        assert result is None

    @pytest.mark.asyncio
    async def test_allocate_key_distribution(self, manager):
        """키 분배가 균등한지 확인"""
        # 6개 회의 할당
        for i in range(6):
            await manager.allocate_key(f"meeting-{i}")

        status = await manager.get_status()

        # 모든 키가 2개씩 사용
        for key_index in range(3):
            assert status[key_index]["meetings"] == 2
            assert status[key_index]["available"] == 0

    @pytest.mark.asyncio
    async def test_allocate_after_ttl_expiration(self, manager, mock_redis):
        """TTL 만료 후 재할당 가능"""
        manager.meeting_key_ttl = 10

        key1 = await manager.allocate_key("meeting-1")
        assert key1 == 0

        mock_redis.advance_time(11)

        key2 = await manager.allocate_key("meeting-2")
        assert key2 == 0

        status = await manager.get_status()
        assert status[0]["meetings"] == 1

    # ===== 키 반환 테스트 =====

    @pytest.mark.asyncio
    async def test_release_key_success(self, manager):
        """키 반환 성공"""
        await manager.allocate_key("meeting-1")
        released = await manager.release_key("meeting-1")
        assert released is True

        # 반환 후 상태 확인
        status = await manager.get_status()
        assert status[0]["meetings"] == 0

    @pytest.mark.asyncio
    async def test_release_key_not_found(self, manager):
        """없는 키 반환 시 False"""
        released = await manager.release_key("unknown-meeting")
        assert released is False

    @pytest.mark.asyncio
    async def test_release_key_idempotent(self, manager):
        """이미 반환된 키 재반환 시 False"""
        await manager.allocate_key("meeting-1")
        first_release = await manager.release_key("meeting-1")
        second_release = await manager.release_key("meeting-1")

        assert first_release is True
        assert second_release is False

    @pytest.mark.asyncio
    async def test_release_key_reusable(self, manager):
        """반환 후 다시 할당 가능"""
        # 모두 소진
        for i in range(6):
            await manager.allocate_key(f"meeting-{i}")

        # 할당 불가 확인
        assert await manager.allocate_key("meeting-overflow") is None

        # 하나 반환
        await manager.release_key("meeting-0")

        # 새 할당 가능 (반환된 키 0 재사용)
        key = await manager.allocate_key("meeting-new")
        assert key == 0

    @pytest.mark.asyncio
    async def test_release_after_ttl_expiration(self, manager, mock_redis):
        """TTL 만료 후 release 호출 시 누수 없음"""
        manager.meeting_key_ttl = 5

        await manager.allocate_key("meeting-1")
        mock_redis.advance_time(6)

        released = await manager.release_key("meeting-1")
        assert released is False

        status = await manager.get_status()
        assert status[0]["meetings"] == 0

    # ===== 키 인덱스 조회 테스트 =====

    @pytest.mark.asyncio
    async def test_get_key_index_exists(self, manager):
        """할당된 키 인덱스 조회"""
        await manager.allocate_key("meeting-1")
        key_index = await manager.get_key_index("meeting-1")
        assert key_index == 0

    @pytest.mark.asyncio
    async def test_get_key_index_not_found(self, manager):
        """없는 회의 조회 시 None"""
        key_index = await manager.get_key_index("unknown")
        assert key_index is None

    # ===== 상태 조회 테스트 =====

    @pytest.mark.asyncio
    async def test_get_status_initial(self, manager):
        """초기 상태 조회"""
        status = await manager.get_status()

        assert len(status) == 3
        for key_index in range(3):
            assert status[key_index]["meetings"] == 0
            assert status[key_index]["available"] == 2

    @pytest.mark.asyncio
    async def test_get_status_after_allocations(self, manager):
        """할당 후 상태 조회"""
        await manager.allocate_key("meeting-1")
        await manager.allocate_key("meeting-2")

        status = await manager.get_status()

        # key 0: 1개, key 1: 1개
        assert status[0]["meetings"] == 1
        assert status[0]["available"] == 1
        assert status[1]["meetings"] == 1
        assert status[1]["available"] == 1
        assert status[2]["meetings"] == 0
        assert status[2]["available"] == 2

    @pytest.mark.asyncio
    async def test_get_status_excludes_expired_meetings(self, manager, mock_redis):
        """get_status()가 TTL 만료된 항목을 제외하는지 확인"""
        manager.meeting_key_ttl = 10

        # 2개 할당
        await manager.allocate_key("meeting-1")
        await manager.allocate_key("meeting-2")

        status = await manager.get_status()
        assert status[0]["meetings"] == 1
        assert status[1]["meetings"] == 1

        # 시간 경과 (TTL 만료)
        mock_redis.advance_time(11)

        # get_status()는 만료된 항목을 제외해야 함
        status = await manager.get_status()
        assert status[0]["meetings"] == 0
        assert status[1]["meetings"] == 0
        assert status[0]["available"] == 2
        assert status[1]["available"] == 2

    # ===== 경계값 테스트 =====

    @pytest.mark.asyncio
    async def test_single_key_manager(self):
        """키 1개 매니저 (MAX_MEETINGS_PER_KEY=2 고정)"""
        mock_redis = MockRedisForClovaKeyManager()
        manager = ClovaKeyManager(redis=mock_redis, total_keys=1)

        key = await manager.allocate_key("meeting-1")
        assert key == 0

        # 두 번째도 같은 키 할당 (키당 2회의 가능)
        key = await manager.allocate_key("meeting-2")
        assert key == 0

        # 세 번째는 None
        key = await manager.allocate_key("meeting-3")
        assert key is None

    @pytest.mark.asyncio
    async def test_many_keys_manager(self):
        """키 10개 매니저 (MAX_MEETINGS_PER_KEY=2 고정)"""
        mock_redis = MockRedisForClovaKeyManager()
        manager = ClovaKeyManager(redis=mock_redis, total_keys=10)

        # 20개 모두 할당 가능 (10키 × 2회의)
        for i in range(20):
            key = await manager.allocate_key(f"meeting-{i}")
            assert key == i % 10  # 0,1,2,...,9,0,1,2,...,9

        # 21번째는 None
        assert await manager.allocate_key("meeting-20") is None


class TestGetClovaKeyManager:
    """get_clova_key_manager 싱글톤 팩토리 테스트"""

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self, monkeypatch):
        """싱글톤 패턴: 같은 인스턴스 반환"""
        import app.services.clova_key_manager as module

        # 기존 싱글톤 초기화
        module._key_manager = None

        # Mock Redis
        mock_redis = MockRedisForClovaKeyManager()
        mock_get_redis = AsyncMock(return_value=mock_redis)
        monkeypatch.setattr("app.services.clova_key_manager.get_redis", mock_get_redis)

        # Mock Settings
        class MockSettings:
            clova_stt_key_count = 5

        mock_get_settings = lambda: MockSettings()
        monkeypatch.setattr("app.core.config.get_settings", mock_get_settings)

        # 첫 번째 호출
        from app.services.clova_key_manager import get_clova_key_manager

        manager1 = await get_clova_key_manager()

        # 두 번째 호출
        manager2 = await get_clova_key_manager()

        # 같은 인스턴스여야 함
        assert manager1 is manager2

        # 정리
        module._key_manager = None
