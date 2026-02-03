"""Clova STT API Key Manager

인메모리 기반 동적 API 키 할당 관리.
각 키당 최대 2개 회의까지 지원하여 동시 세션 제한(15개/키)을 준수.
"""

import logging

logger = logging.getLogger(__name__)


class ClovaKeyManager:
    """Clova STT API 키 할당 관리자

    인메모리로 API 키 할당 상태를 관리합니다.
    Least Connections 알고리즘으로 가장 여유 있는 키를 할당합니다.
    """

    # 회의당 평균 7명 가정
    MAX_MEETINGS_PER_KEY = 2

    def __init__(self, total_keys: int = 5):
        """
        Args:
            total_keys: 사용 가능한 API 키 총 개수
        """
        self.total_keys = total_keys
        self.max_meetings_per_key = self.MAX_MEETINGS_PER_KEY

        # 인메모리 상태
        self._key_usage: dict[int, int] = {}  # key_index -> meeting count
        self._meeting_keys: dict[str, int] = {}  # meeting_id -> key_index

    async def allocate_key(self, meeting_id: str) -> int | None:
        """회의에 API 키 할당

        Least Connections 알고리즘으로 가장 여유 있는 키를 선택합니다.

        Args:
            meeting_id: 회의 ID

        Returns:
            할당된 키 인덱스 (0-4) 또는 None (사용 가능한 키 없음)
        """
        # 이미 할당된 키가 있는지 확인
        if meeting_id in self._meeting_keys:
            existing = self._meeting_keys[meeting_id]
            logger.debug(f"이미 할당된 키 사용: meeting={meeting_id}, key_index={existing}")
            return existing

        # Least Connections: 가장 여유 있는 키 찾기
        best_key_index: int | None = None
        min_meetings = self.max_meetings_per_key

        for key_index in range(self.total_keys):
            current_meetings = self._key_usage.get(key_index, 0)

            if current_meetings < min_meetings:
                min_meetings = current_meetings
                best_key_index = key_index

                # 빈 키를 찾으면 바로 사용
                if current_meetings == 0:
                    break

        if best_key_index is None:
            logger.warning(f"사용 가능한 API 키 없음: meeting={meeting_id}")
            return None

        # 할당
        self._key_usage[best_key_index] = self._key_usage.get(best_key_index, 0) + 1
        self._meeting_keys[meeting_id] = best_key_index

        logger.info(f"API 키 할당: meeting={meeting_id}, key_index={best_key_index}")
        return best_key_index

    async def release_key(self, meeting_id: str) -> bool:
        """회의의 API 키 반환

        Args:
            meeting_id: 회의 ID

        Returns:
            반환 성공 여부
        """
        if meeting_id not in self._meeting_keys:
            logger.debug(f"반환할 키 없음 (이미 반환됨): meeting={meeting_id}")
            return False

        key_index = self._meeting_keys.pop(meeting_id)
        self._key_usage[key_index] = max(0, self._key_usage.get(key_index, 1) - 1)

        logger.info(f"API 키 반환: meeting={meeting_id}, key_index={key_index}")
        return True

    async def get_key_index(self, meeting_id: str) -> int | None:
        """회의에 할당된 키 인덱스 조회

        Args:
            meeting_id: 회의 ID

        Returns:
            할당된 키 인덱스 또는 None
        """
        return self._meeting_keys.get(meeting_id)

    async def get_status(self) -> dict:
        """전체 키 사용 현황 조회

        Returns:
            키별 사용 현황 딕셔너리
        """
        status = {}
        for key_index in range(self.total_keys):
            meetings = self._key_usage.get(key_index, 0)
            status[key_index] = {
                "meetings": meetings,
                "available": self.max_meetings_per_key - meetings,
            }
        return status


# 싱글톤 인스턴스
_key_manager: ClovaKeyManager | None = None


def get_clova_key_manager() -> ClovaKeyManager:
    """ClovaKeyManager 싱글톤 반환"""
    global _key_manager
    if _key_manager is None:
        from app.core.config import get_settings

        settings = get_settings()
        _key_manager = ClovaKeyManager(
            total_keys=getattr(settings, "clova_stt_key_count", 5),
        )
    return _key_manager
