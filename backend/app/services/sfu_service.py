"""SFU (Selective Forwarding Unit) 서비스 - aiortc 기반 녹음

하이브리드 아키텍처:
- 실시간 통화: 기존 Mesh P2P (클라이언트 간 직접 연결)
- 녹음: 서버로 별도 연결 (aiortc RTCPeerConnection + MediaRecorder)
"""

import logging
from uuid import UUID

from aiortc import RTCPeerConnection
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recording import MeetingRecording
from app.services.webrtc import RecordingPersistence, WebRTCRecordingConnection

logger = logging.getLogger(__name__)


class RecordingSession:
    """개별 사용자의 녹음 세션 코디네이터

    WebRTC 연결 관리(WebRTCRecordingConnection)와
    녹음 파일 저장(RecordingPersistence)을 조율합니다.

    Refactored: 7가지 책임을 가진 God Class에서 2개의 전문 클래스를 사용하는
    코디네이터로 리팩토링되었습니다.
    """

    def __init__(self, meeting_id: UUID, user_id: UUID):
        """
        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
        """
        self.meeting_id = meeting_id
        self.user_id = user_id
        # Composition: 연결 관리와 저장 책임을 위임
        self.connection = WebRTCRecordingConnection(meeting_id, user_id)
        self.persistence = RecordingPersistence()

    async def setup(self) -> RTCPeerConnection:
        """PeerConnection 설정 (연결 관리 클래스에 위임)

        Returns:
            설정된 RTCPeerConnection 인스턴스
        """
        return await self.connection.setup()

    async def handle_offer(self, sdp: dict) -> dict:
        """클라이언트 Offer 처리 및 Answer 반환 (연결 관리 클래스에 위임)

        Args:
            sdp: {"sdp": "...", "type": "offer"}

        Returns:
            Answer SDP: {"sdp": "...", "type": "answer"}
        """
        return await self.connection.handle_offer(sdp)

    async def handle_ice_candidate(self, candidate: dict) -> None:
        """ICE Candidate 추가 (연결 관리 클래스에 위임)

        Args:
            candidate: ICE candidate 객체 (브라우저 형식)
        """
        await self.connection.add_ice_candidate(candidate)

    async def stop_and_save(self, db: AsyncSession) -> MeetingRecording | None:
        """녹음 중지 및 저장 (연결 중지 + 저장 클래스에 위임)

        Args:
            db: 데이터베이스 세션

        Returns:
            저장된 MeetingRecording 또는 None
        """
        # 1. 녹음 중지 (연결 관리 클래스)
        ended_at = await self.connection.stop_recorder()
        if not ended_at:
            return None

        # 2. 파일 저장 (저장 클래스)
        temp_file_path = self.connection.get_temp_file_path()
        started_at = self.connection.get_started_at()

        if not temp_file_path or not started_at:
            logger.warning(f"[RecordingSession] Missing temp file or started_at for user {self.user_id}")
            return None

        return await self.persistence.save_recording(
            meeting_id=self.meeting_id,
            user_id=self.user_id,
            temp_file_path=temp_file_path,
            started_at=started_at,
            ended_at=ended_at,
            db=db,
        )

    async def close(self) -> None:
        """리소스 정리 (연결 관리 클래스에 위임)"""
        await self.connection.close()


class SFURoom:
    """단일 회의실의 녹음 관리

    하이브리드 구조:
    - 기존 Mesh 시그널링은 webrtc.py에서 처리 (변경 없음)
    - 여기서는 녹음 전용 연결만 관리
    """

    def __init__(self, meeting_id: UUID):
        self.meeting_id = meeting_id
        # 녹음 세션: user_id -> RecordingSession
        self._recording_sessions: dict[str, RecordingSession] = {}
        # 기존 Mesh용 피어 추적 (호환성 유지)
        self._peer_connections: dict[str, object] = {}

    def get_or_create_recording_session(self, user_id: UUID) -> RecordingSession:
        """사용자 녹음 세션 조회 또는 생성"""
        user_key = str(user_id)
        if user_key not in self._recording_sessions:
            self._recording_sessions[user_key] = RecordingSession(self.meeting_id, user_id)
            logger.info(f"[SFURoom] Recording session created for user {user_id}")
        return self._recording_sessions[user_key]

    async def handle_recording_offer(self, user_id: UUID, sdp: dict) -> dict:
        """녹음용 Offer 처리

        Args:
            user_id: 사용자 ID
            sdp: SDP Offer

        Returns:
            SDP Answer
        """
        session = self.get_or_create_recording_session(user_id)
        return await session.handle_offer(sdp)

    async def handle_recording_ice(self, user_id: UUID, candidate: dict) -> None:
        """녹음용 ICE Candidate 처리

        Args:
            user_id: 사용자 ID
            candidate: ICE Candidate
        """
        user_key = str(user_id)
        if user_key in self._recording_sessions:
            await self._recording_sessions[user_key].handle_ice_candidate(candidate)

    async def stop_user_recording(self, user_id: UUID, db: AsyncSession) -> MeetingRecording | None:
        """특정 사용자 녹음 중지 및 저장

        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션

        Returns:
            저장된 MeetingRecording 또는 None
        """
        user_key = str(user_id)
        if user_key in self._recording_sessions:
            session = self._recording_sessions[user_key]
            recording = await session.stop_and_save(db)
            await session.close()
            del self._recording_sessions[user_key]
            logger.info(f"[SFURoom] Recording stopped for user {user_id}")
            return recording
        return None

    # === 기존 Mesh 호환성 유지 ===

    async def add_peer(self, user_id: UUID) -> None:
        """피어 추가 (Mesh 호환)"""
        user_key = str(user_id)
        self._peer_connections[user_key] = None
        logger.info(f"[SFURoom] Peer added: {user_id}")

    async def remove_peer(self, user_id: UUID) -> None:
        """피어 제거 (Mesh 호환)"""
        user_key = str(user_id)
        if user_key in self._peer_connections:
            del self._peer_connections[user_key]
        logger.info(f"[SFURoom] Peer removed: {user_id}")

    async def close(self, db: AsyncSession | None = None) -> list[MeetingRecording]:
        """회의실 종료 및 모든 녹음 저장

        Args:
            db: 데이터베이스 세션 (녹음 저장용)

        Returns:
            저장된 녹음 목록
        """
        recordings = []

        # 녹음 세션 정리
        for user_key in list(self._recording_sessions.keys()):
            session = self._recording_sessions[user_key]
            try:
                if db:
                    recording = await session.stop_and_save(db)
                    if recording:
                        recordings.append(recording)
                await session.close()
            except Exception as e:
                logger.error(f"[SFURoom] Failed to close recording session: {e}")
            del self._recording_sessions[user_key]

        # Mesh 피어 정리
        self._peer_connections.clear()

        logger.info(f"[SFURoom] Room closed: {self.meeting_id}, {len(recordings)} recordings saved")
        return recordings


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
            logger.info(f"[SFUService] Room created: {meeting_id}")
        return self._rooms[meeting_key]

    def get_room(self, meeting_id: UUID) -> SFURoom | None:
        """회의실 조회"""
        meeting_key = str(meeting_id)
        return self._rooms.get(meeting_key)

    async def close_room(self, meeting_id: UUID, db: AsyncSession | None = None) -> list[MeetingRecording]:
        """회의실 종료 및 모든 녹음 저장

        Args:
            meeting_id: 회의 ID
            db: 데이터베이스 세션

        Returns:
            저장된 녹음 목록
        """
        meeting_key = str(meeting_id)
        recordings = []

        if meeting_key in self._rooms:
            recordings = await self._rooms[meeting_key].close(db)
            del self._rooms[meeting_key]
            logger.info(f"[SFUService] Room removed: {meeting_id}")

        return recordings


# 싱글톤 인스턴스
sfu_service = SFUService()
