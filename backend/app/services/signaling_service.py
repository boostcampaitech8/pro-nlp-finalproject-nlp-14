"""WebSocket 시그널링 서비스 - 연결 관리 및 메시지 라우팅"""

import json
import logging
from uuid import UUID

from fastapi import WebSocket

from app.schemas.webrtc import RoomParticipant

logger = logging.getLogger(__name__)


class ConnectionManager:
    """회의별 WebSocket 연결 관리"""

    def __init__(self):
        # meeting_id -> {user_id -> WebSocket}
        self._connections: dict[str, dict[str, WebSocket]] = {}
        # meeting_id -> {user_id -> RoomParticipant}
        self._participants: dict[str, dict[str, RoomParticipant]] = {}

    async def connect(
        self,
        meeting_id: UUID,
        user_id: UUID,
        user_name: str,
        role: str,
        websocket: WebSocket,
    ) -> None:
        """WebSocket 연결 등록"""
        await websocket.accept()

        meeting_key = str(meeting_id)
        user_key = str(user_id)

        if meeting_key not in self._connections:
            self._connections[meeting_key] = {}
            self._participants[meeting_key] = {}

        self._connections[meeting_key][user_key] = websocket
        self._participants[meeting_key][user_key] = RoomParticipant(
            user_id=user_id,
            user_name=user_name,
            role=role,
            audio_muted=False,
        )

        logger.info(f"User {user_id} connected to meeting {meeting_id}")

    async def disconnect(self, meeting_id: UUID, user_id: UUID) -> None:
        """WebSocket 연결 해제"""
        meeting_key = str(meeting_id)
        user_key = str(user_id)

        if meeting_key in self._connections:
            self._connections[meeting_key].pop(user_key, None)
            self._participants[meeting_key].pop(user_key, None)

            # 회의에 아무도 없으면 정리
            if not self._connections[meeting_key]:
                del self._connections[meeting_key]
                del self._participants[meeting_key]

        logger.info(f"User {user_id} disconnected from meeting {meeting_id}")

    async def broadcast(
        self,
        meeting_id: UUID,
        message: dict,
        exclude_user_id: UUID | None = None,
    ) -> None:
        """회의 참여자 전체에게 메시지 전송 (특정 사용자 제외 가능)"""
        meeting_key = str(meeting_id)
        exclude_key = str(exclude_user_id) if exclude_user_id else None

        if meeting_key not in self._connections:
            return

        disconnected = []
        for user_key, websocket in self._connections[meeting_key].items():
            if user_key == exclude_key:
                continue
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to {user_key}: {e}")
                disconnected.append(user_key)

        # 연결이 끊긴 사용자 정리
        for user_key in disconnected:
            self._connections[meeting_key].pop(user_key, None)
            self._participants[meeting_key].pop(user_key, None)

    async def send_to_user(
        self,
        meeting_id: UUID,
        user_id: UUID,
        message: dict,
    ) -> bool:
        """특정 사용자에게 메시지 전송"""
        meeting_key = str(meeting_id)
        user_key = str(user_id)

        if meeting_key not in self._connections:
            return False

        websocket = self._connections[meeting_key].get(user_key)
        if not websocket:
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send message to {user_id}: {e}")
            self._connections[meeting_key].pop(user_key, None)
            self._participants[meeting_key].pop(user_key, None)
            return False

    def get_participants(self, meeting_id: UUID) -> list[RoomParticipant]:
        """회의 참여자 목록 조회"""
        meeting_key = str(meeting_id)
        if meeting_key not in self._participants:
            return []
        return list(self._participants[meeting_key].values())

    def get_participant(self, meeting_id: UUID, user_id: UUID) -> RoomParticipant | None:
        """특정 참여자 조회"""
        meeting_key = str(meeting_id)
        user_key = str(user_id)
        if meeting_key not in self._participants:
            return None
        return self._participants[meeting_key].get(user_key)

    def update_mute_status(self, meeting_id: UUID, user_id: UUID, muted: bool) -> None:
        """참여자 음소거 상태 업데이트"""
        meeting_key = str(meeting_id)
        user_key = str(user_id)
        if meeting_key in self._participants and user_key in self._participants[meeting_key]:
            self._participants[meeting_key][user_key].audio_muted = muted

    def get_connection_count(self, meeting_id: UUID) -> int:
        """회의 연결 수 조회"""
        meeting_key = str(meeting_id)
        if meeting_key not in self._connections:
            return 0
        return len(self._connections[meeting_key])

    async def close_all_connections(self, meeting_id: UUID, reason: str = "Meeting ended") -> None:
        """회의의 모든 연결 종료"""
        meeting_key = str(meeting_id)
        if meeting_key not in self._connections:
            return

        # 종료 메시지 전송
        end_message = {
            "type": "meeting-ended",
            "reason": reason,
        }

        for websocket in self._connections[meeting_key].values():
            try:
                await websocket.send_json(end_message)
                await websocket.close(code=1000, reason=reason)
            except Exception:
                pass

        # 정리
        del self._connections[meeting_key]
        del self._participants[meeting_key]

        logger.info(f"All connections closed for meeting {meeting_id}")


# 싱글톤 인스턴스
connection_manager = ConnectionManager()
