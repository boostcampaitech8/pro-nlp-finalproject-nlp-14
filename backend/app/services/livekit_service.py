"""LiveKit SFU 서비스 - 토큰 생성, 룸 관리, 녹음 제어

LiveKit SDK를 사용하여:
- 참여자 액세스 토큰 생성
- 룸 생성/삭제
- Egress(서버 측 녹음) 시작/중지
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

        # 진행 중인 Egress 추적 (meeting_id -> egress_id)
        self._active_egress: dict[str, str] = {}

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
            room_service = api.RoomService(self._ws_url, self._api_key, self._api_secret)
            await room_service.create_room(
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
            room_service = api.RoomService(self._ws_url, self._api_key, self._api_secret)
            await room_service.delete_room(api.DeleteRoomRequest(room=room_name))
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
            room_service = api.RoomService(self._ws_url, self._api_key, self._api_secret)
            response = await room_service.list_participants(
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

    async def start_room_recording(
        self,
        meeting_id: UUID,
        room_name: str,
    ) -> str | None:
        """룸 녹음 시작 (Room Composite Egress)

        모든 참여자의 오디오를 하나의 파일로 녹음합니다.

        Args:
            meeting_id: 회의 ID (파일명에 사용)
            room_name: 룸 이름

        Returns:
            Egress ID 또는 None (실패 시)
        """
        if not self.is_configured:
            logger.warning("[LiveKit] Not configured, skipping recording")
            return None

        meeting_key = str(meeting_id)

        # 이미 녹음 중인지 확인
        if meeting_key in self._active_egress:
            logger.warning(f"[LiveKit] Recording already active for meeting {meeting_id}")
            return self._active_egress[meeting_key]

        try:
            egress_service = api.EgressService(self._ws_url, self._api_key, self._api_secret)

            # S3 업로드 설정 (MinIO)
            settings = get_settings()
            s3_upload = api.S3Upload(
                access_key=settings.minio_access_key,
                secret=settings.minio_secret_key,
                endpoint=f"http://{settings.minio_endpoint}",
                bucket="recordings",
                force_path_style=True,
            )

            # Room Composite Egress - 모든 트랙 믹싱
            request = api.RoomCompositeEgressRequest(
                room_name=room_name,
                audio_only=True,  # 오디오만 녹음
                file_outputs=[
                    api.EncodedFileOutput(
                        file_type=api.EncodedFileType.OGG,  # OGG Opus 포맷
                        filepath=f"meetings/{meeting_id}/composite-{{time}}.ogg",
                        s3=s3_upload,
                    )
                ],
            )

            info = await egress_service.start_room_composite_egress(request)
            egress_id = info.egress_id

            self._active_egress[meeting_key] = egress_id
            logger.info(f"[LiveKit] Recording started: meeting={meeting_id}, egress={egress_id}")

            return egress_id

        except Exception as e:
            logger.error(f"[LiveKit] Failed to start recording for {meeting_id}: {e}")
            return None

    async def stop_room_recording(self, meeting_id: UUID) -> bool:
        """룸 녹음 중지

        Args:
            meeting_id: 회의 ID

        Returns:
            성공 여부
        """
        if not self.is_configured:
            return False

        meeting_key = str(meeting_id)

        if meeting_key not in self._active_egress:
            logger.warning(f"[LiveKit] No active recording for meeting {meeting_id}")
            return False

        egress_id = self._active_egress[meeting_key]

        try:
            egress_service = api.EgressService(self._ws_url, self._api_key, self._api_secret)
            await egress_service.stop_egress(api.StopEgressRequest(egress_id=egress_id))

            del self._active_egress[meeting_key]
            logger.info(f"[LiveKit] Recording stopped: meeting={meeting_id}, egress={egress_id}")

            return True

        except Exception as e:
            logger.error(f"[LiveKit] Failed to stop recording for {meeting_id}: {e}")
            return False

    async def start_track_recording(
        self,
        meeting_id: UUID,
        room_name: str,
        user_id: UUID,
        track_id: str,
    ) -> str | None:
        """개별 트랙 녹음 시작 (Track Egress)

        특정 참여자의 오디오 트랙만 녹음합니다.
        VAD 기반 실시간 STT 준비용.

        Args:
            meeting_id: 회의 ID
            room_name: 룸 이름
            user_id: 사용자 ID
            track_id: 트랙 ID

        Returns:
            Egress ID 또는 None
        """
        if not self.is_configured:
            return None

        try:
            egress_service = api.EgressService(self._ws_url, self._api_key, self._api_secret)

            settings = get_settings()
            s3_upload = api.S3Upload(
                access_key=settings.minio_access_key,
                secret=settings.minio_secret_key,
                endpoint=f"http://{settings.minio_endpoint}",
                bucket="recordings",
                force_path_style=True,
            )

            request = api.TrackEgressRequest(
                room_name=room_name,
                track_id=track_id,
                file=api.DirectFileOutput(
                    filepath=f"meetings/{meeting_id}/{user_id}/{{track_id}}-{{time}}.ogg",
                    s3=s3_upload,
                ),
            )

            info = await egress_service.start_track_egress(request)
            logger.info(f"[LiveKit] Track recording started: user={user_id}, track={track_id}")

            return info.egress_id

        except Exception as e:
            logger.error(f"[LiveKit] Failed to start track recording: {e}")
            return None

    def get_ws_url_for_client(self) -> str:
        """클라이언트용 WebSocket URL 반환"""
        return self._external_url

    @staticmethod
    def get_room_name(meeting_id: UUID) -> str:
        """회의 ID로 룸 이름 생성"""
        return f"meeting-{meeting_id}"


# 싱글톤 인스턴스
livekit_service = LiveKitService()
