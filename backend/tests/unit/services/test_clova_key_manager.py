"""Clova Key Manager 단위 테스트

테스트 케이스:
- 키 할당: 성공, Least Connections, 멱등성, 소진
- 키 반환: 성공, 없는 키, 반환 후 재사용
- 상태 조회
"""

import pytest

from app.services.clova_key_manager import ClovaKeyManager


class TestClovaKeyManager:
    """ClovaKeyManager 단위 테스트"""

    @pytest.fixture
    def manager(self):
        """테스트용 매니저 (3개 키, 키당 2회의 - MAX_MEETINGS_PER_KEY=2 고정)"""
        return ClovaKeyManager(total_keys=3)

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

    # ===== 경계값 테스트 =====

    @pytest.mark.asyncio
    async def test_single_key_manager(self):
        """키 1개 매니저 (MAX_MEETINGS_PER_KEY=2 고정)"""
        manager = ClovaKeyManager(total_keys=1)

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
        manager = ClovaKeyManager(total_keys=10)

        # 20개 모두 할당 가능 (10키 × 2회의)
        for i in range(20):
            key = await manager.allocate_key(f"meeting-{i}")
            assert key == i % 10  # 0,1,2,...,9,0,1,2,...,9

        # 21번째는 None
        assert await manager.allocate_key("meeting-20") is None
