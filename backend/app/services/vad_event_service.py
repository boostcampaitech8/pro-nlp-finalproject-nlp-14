"""VAD 이벤트 서비스 - 클라이언트 VAD 이벤트 처리

클라이언트에서 전송되는 발화 시작/끝 이벤트를 처리합니다.
현재는 이벤트 저장만 수행하며, 추후 실시간 STT 연동에 사용됩니다.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class VADSegment:
    """발화 세그먼트"""

    start_ms: int
    end_ms: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VADEvent:
    """VAD 이벤트"""

    meeting_id: UUID
    user_id: UUID
    event_type: Literal["speech_start", "speech_end"]
    timestamp: datetime
    segment_start_ms: int | None = None
    segment_end_ms: int | None = None


class VADEventService:
    """VAD 이벤트 처리 서비스

    실시간 STT 준비용으로 다음 기능을 제공합니다:
    - 발화 이벤트 수집 및 저장
    - 세그먼트 메타데이터 관리
    - 추후 실시간 STT 트리거 연동
    """

    def __init__(self):
        # 회의별 발화 세그먼트 저장 (meeting_id -> user_id -> segments)
        self._segments: dict[str, dict[str, list[VADSegment]]] = {}

        # 진행 중인 발화 추적 (meeting_id -> user_id -> start_ms)
        self._speaking: dict[str, dict[str, int]] = {}

    async def handle_vad_event(self, event: VADEvent) -> None:
        """VAD 이벤트 처리

        Args:
            event: VAD 이벤트
        """
        meeting_key = str(event.meeting_id)
        user_key = str(event.user_id)

        # 회의별 저장소 초기화
        if meeting_key not in self._segments:
            self._segments[meeting_key] = {}
            self._speaking[meeting_key] = {}

        if user_key not in self._segments[meeting_key]:
            self._segments[meeting_key][user_key] = []

        if event.event_type == "speech_start":
            await self._handle_speech_start(meeting_key, user_key, event)
        elif event.event_type == "speech_end":
            await self._handle_speech_end(meeting_key, user_key, event)

    async def _handle_speech_start(
        self,
        meeting_key: str,
        user_key: str,
        event: VADEvent,
    ) -> None:
        """발화 시작 처리"""
        if event.segment_start_ms is not None:
            self._speaking[meeting_key][user_key] = event.segment_start_ms
            logger.debug(
                f"[VAD] Speech started: meeting={meeting_key}, "
                f"user={user_key}, start_ms={event.segment_start_ms}"
            )

        # TODO: 실시간 STT 구현 시 여기서 스트리밍 시작
        # await self._start_realtime_stt(meeting_key, user_key)

    async def _handle_speech_end(
        self,
        meeting_key: str,
        user_key: str,
        event: VADEvent,
    ) -> None:
        """발화 종료 처리"""
        if event.segment_start_ms is not None and event.segment_end_ms is not None:
            segment = VADSegment(
                start_ms=event.segment_start_ms,
                end_ms=event.segment_end_ms,
                timestamp=event.timestamp,
            )
            self._segments[meeting_key][user_key].append(segment)

            duration_ms = event.segment_end_ms - event.segment_start_ms
            logger.debug(
                f"[VAD] Speech ended: meeting={meeting_key}, "
                f"user={user_key}, duration={duration_ms}ms"
            )

        # 진행 중 발화 상태 제거
        if user_key in self._speaking.get(meeting_key, {}):
            del self._speaking[meeting_key][user_key]

        # TODO: 실시간 STT 구현 시 여기서 세그먼트 STT 처리
        # await self._process_segment_stt(meeting_key, user_key, segment)

    def get_user_segments(self, meeting_id: UUID, user_id: UUID) -> list[VADSegment]:
        """사용자의 발화 세그먼트 조회

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID

        Returns:
            발화 세그먼트 목록
        """
        meeting_key = str(meeting_id)
        user_key = str(user_id)

        return self._segments.get(meeting_key, {}).get(user_key, [])

    def get_meeting_segments(self, meeting_id: UUID) -> dict[str, list[VADSegment]]:
        """회의의 모든 발화 세그먼트 조회

        Args:
            meeting_id: 회의 ID

        Returns:
            사용자별 발화 세그먼트 (user_id -> segments)
        """
        meeting_key = str(meeting_id)
        return self._segments.get(meeting_key, {})

    def is_user_speaking(self, meeting_id: UUID, user_id: UUID) -> bool:
        """사용자가 현재 발화 중인지 확인

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID

        Returns:
            발화 중 여부
        """
        meeting_key = str(meeting_id)
        user_key = str(user_id)
        return user_key in self._speaking.get(meeting_key, {})

    def get_speaking_users(self, meeting_id: UUID) -> list[str]:
        """현재 발화 중인 사용자 목록

        Args:
            meeting_id: 회의 ID

        Returns:
            발화 중인 사용자 ID 목록
        """
        meeting_key = str(meeting_id)
        return list(self._speaking.get(meeting_key, {}).keys())

    async def store_meeting_vad_metadata(
        self,
        meeting_id: UUID,
    ) -> dict[str, list[dict]]:
        """회의 종료 시 VAD 메타데이터 저장

        회의 종료 시 호출하여 모든 VAD 세그먼트를 영구 저장합니다.

        Args:
            meeting_id: 회의 ID

        Returns:
            저장된 메타데이터 (user_id -> segments)
        """
        meeting_key = str(meeting_id)

        if meeting_key not in self._segments:
            return {}

        # 세그먼트를 직렬화 가능한 형태로 변환
        metadata = {}
        for user_key, segments in self._segments[meeting_key].items():
            metadata[user_key] = [
                {
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                    "timestamp": seg.timestamp.isoformat(),
                }
                for seg in segments
            ]

        # 메모리에서 정리
        del self._segments[meeting_key]
        if meeting_key in self._speaking:
            del self._speaking[meeting_key]

        logger.info(
            f"[VAD] Meeting metadata stored: meeting={meeting_id}, "
            f"users={len(metadata)}, "
            f"total_segments={sum(len(s) for s in metadata.values())}"
        )

        return metadata

    def clear_meeting(self, meeting_id: UUID) -> None:
        """회의 데이터 정리

        Args:
            meeting_id: 회의 ID
        """
        meeting_key = str(meeting_id)

        if meeting_key in self._segments:
            del self._segments[meeting_key]

        if meeting_key in self._speaking:
            del self._speaking[meeting_key]

        logger.info(f"[VAD] Meeting data cleared: {meeting_id}")


# 싱글톤 인스턴스
vad_event_service = VADEventService()
