"""SFU (Selective Forwarding Unit) 서비스
현재는 Mesh 시그널링으로 구현, Week 4에서 실제 SFU + 녹음 기능 추가 예정
"""

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class SFURoom:
    """단일 회의실의 SFU 관리

    현재 구현:
    - Mesh 시그널링: 클라이언트 간 직접 PeerConnection
    - 서버는 시그널링만 중계

    추후 구현 (Week 4):
    - 서버 측 PeerConnection (aiortc)
    - 각 참여자 오디오 트랙 수신
    - 발화자별 개별 녹음
    """

    def __init__(self, meeting_id: UUID):
        self.meeting_id = meeting_id
        # user_id -> peer_connection (추후 aiortc RTCPeerConnection)
        self._peer_connections: dict[str, object] = {}
        # user_id -> audio_track (추후 MediaStreamTrack)
        self._audio_tracks: dict[str, object] = {}

    async def add_peer(self, user_id: UUID) -> None:
        """피어 추가 (추후 PeerConnection 생성)"""
        user_key = str(user_id)
        self._peer_connections[user_key] = None  # 추후 RTCPeerConnection
        logger.info(f"Peer added: {user_id} in meeting {self.meeting_id}")

    async def remove_peer(self, user_id: UUID) -> None:
        """피어 제거 및 정리"""
        user_key = str(user_id)

        # 트랙 정리
        if user_key in self._audio_tracks:
            del self._audio_tracks[user_key]

        # PeerConnection 정리
        if user_key in self._peer_connections:
            # 추후: pc.close() 호출
            del self._peer_connections[user_key]

        logger.info(f"Peer removed: {user_id} from meeting {self.meeting_id}")

    async def handle_offer(self, user_id: UUID, sdp: dict) -> dict | None:
        """SDP Offer 처리 (Mesh 모드에서는 중계만)

        추후 구현:
        - aiortc RTCPeerConnection 생성
        - setRemoteDescription(offer)
        - createAnswer()
        - setLocalDescription(answer)
        - answer 반환
        """
        # Mesh 모드: offer는 다른 클라이언트로 전달됨
        return None

    async def handle_answer(self, user_id: UUID, sdp: dict) -> None:
        """SDP Answer 처리 (Mesh 모드에서는 중계만)

        추후 구현:
        - setRemoteDescription(answer)
        """
        pass

    async def handle_ice_candidate(self, user_id: UUID, candidate: dict) -> None:
        """ICE Candidate 처리 (Mesh 모드에서는 중계만)

        추후 구현:
        - addIceCandidate(candidate)
        """
        pass

    async def close(self) -> None:
        """회의실 종료 및 모든 리소스 정리"""
        for user_key in list(self._peer_connections.keys()):
            await self.remove_peer(UUID(user_key))

        logger.info(f"SFU room closed: {self.meeting_id}")


class SFUService:
    """전체 SFU 관리 서비스"""

    def __init__(self):
        # meeting_id -> SFURoom
        self._rooms: dict[str, SFURoom] = {}

    def get_or_create_room(self, meeting_id: UUID) -> SFURoom:
        """회의실 조회 또는 생성"""
        meeting_key = str(meeting_id)
        if meeting_key not in self._rooms:
            self._rooms[meeting_key] = SFURoom(meeting_id)
            logger.info(f"SFU room created: {meeting_id}")
        return self._rooms[meeting_key]

    def get_room(self, meeting_id: UUID) -> SFURoom | None:
        """회의실 조회"""
        meeting_key = str(meeting_id)
        return self._rooms.get(meeting_key)

    async def close_room(self, meeting_id: UUID) -> None:
        """회의실 종료"""
        meeting_key = str(meeting_id)
        if meeting_key in self._rooms:
            await self._rooms[meeting_key].close()
            del self._rooms[meeting_key]
            logger.info(f"SFU room removed: {meeting_id}")


# 싱글톤 인스턴스
sfu_service = SFUService()
