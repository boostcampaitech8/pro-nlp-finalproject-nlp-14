"""LiveKit SFU 서비스 - 토큰 생성, 룸 관리

LiveKit SDK를 사용하여:
- 참여자 액세스 토큰 생성
- 룸 생성/삭제
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from livekit import api

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LiveKitService:
    """LiveKit 서버 연동 서비스"""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.livekit_api_key
        self._api_secret = settings.livekit_api_secret
        self._ws_url = settings.livekit_ws_url
        self._external_url = settings.livekit_external_url

    @property
    def is_configured(self) -> bool:
        """LiveKit 설정 완료 여부"""
        return bool(self._api_key and self._api_secret)

    def generate_token(
        self,
        room_name: str,
        participant_id: str,
        participant_name: str,
        is_host: bool = False,
        ttl_seconds: int = 3600,
    ) -> str:
        """참여자용 액세스 토큰 생성

        Args:
            room_name: 룸 이름 (meeting-{meeting_id} 형식)
            participant_id: 참여자 ID (user_id)
            participant_name: 참여자 표시 이름
            is_host: 호스트 여부 (룸 관리 권한)
            ttl_seconds: 토큰 유효 시간 (초)

        Returns:
            JWT 토큰 문자열
        """
        if not self.is_configured:
            raise ValueError("LiveKit is not configured")

        # 권한 설정
        grant = api.VideoGrants(
            room=room_name,
            room_join=True,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,  # VAD 이벤트, 채팅 전송용
        )

        if is_host:
            grant.room_admin = True
            grant.room_record = True  # 녹음 제어 권한

        # 새 SDK API: with_* 메서드 체이닝 사용
        token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(participant_id)
            .with_name(participant_name)
            .with_ttl(timedelta(seconds=ttl_seconds))
            .with_grants(grant)
        )

        logger.info(
            f"[LiveKit] Token generated for {participant_name} "
            f"(id={participant_id}, room={room_name}, host={is_host})"
        )

        return token.to_jwt()

    async def create_room(self, room_name: str, max_participants: int = 20) -> bool:
        """LiveKit 룸 생성

        Args:
            room_name: 룸 이름
            max_participants: 최대 참여자 수

        Returns:
            성공 여부
        """
        if not self.is_configured:
            logger.warning("[LiveKit] Not configured, skipping room creation")
            return False

        try:
            async with api.LiveKitAPI(
                self._ws_url, self._api_key, self._api_secret
            ) as lk_api:
                await lk_api.room.create_room(
                    api.CreateRoomRequest(
                        name=room_name,
                        max_participants=max_participants,
                        empty_timeout=300,  # 빈 룸 5분 후 삭제
                    )
                )
            logger.info(f"[LiveKit] Room created: {room_name}")
            return True
        except Exception as e:
            logger.error(f"[LiveKit] Failed to create room {room_name}: {e}")
            return False

    async def delete_room(self, room_name: str) -> bool:
        """LiveKit 룸 삭제

        Args:
            room_name: 룸 이름

        Returns:
            성공 여부
        """
        if not self.is_configured:
            return False

        try:
            async with api.LiveKitAPI(
                self._ws_url, self._api_key, self._api_secret
            ) as lk_api:
                await lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name))
            logger.info(f"[LiveKit] Room deleted: {room_name}")
            return True
        except Exception as e:
            logger.error(f"[LiveKit] Failed to delete room {room_name}: {e}")
            return False

    async def get_room_participants(self, room_name: str) -> list[dict]:
        """룸 참여자 목록 조회

        Args:
            room_name: 룸 이름

        Returns:
            참여자 목록 [{"id": str, "name": str, "joined_at": datetime}, ...]
        """
        if not self.is_configured:
            return []

        try:
            async with api.LiveKitAPI(
                self._ws_url, self._api_key, self._api_secret
            ) as lk_api:
                response = await lk_api.room.list_participants(
                    api.ListParticipantsRequest(room=room_name)
                )
                return [
                    {
                        "id": p.identity,
                        "name": p.name,
                        "joined_at": datetime.fromtimestamp(p.joined_at),
                    }
                    for p in response.participants
                ]
        except Exception as e:
            logger.error(f"[LiveKit] Failed to list participants: {e}")
            return []

    def get_ws_url_for_client(self) -> str:
        """클라이언트용 WebSocket URL 반환"""
        return self._external_url

    @staticmethod
    def get_room_name(meeting_id: UUID) -> str:
        """회의 ID로 룸 이름 생성"""
        return f"meeting-{meeting_id}"


# 싱글톤 인스턴스
livekit_service = LiveKitService()
