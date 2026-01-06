"""SFU (Selective Forwarding Unit) 서비스 - aiortc 기반 녹음

하이브리드 아키텍처:
- 실시간 통화: 기존 Mesh P2P (클라이언트 간 직접 연결)
- 녹음: 서버로 별도 연결 (aiortc RTCPeerConnection + MediaRecorder)
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage_service
from app.core.webrtc_config import ICE_SERVERS
from app.models.recording import MeetingRecording, RecordingStatus

logger = logging.getLogger(__name__)


class RecordingSession:
    """개별 사용자의 녹음 세션

    각 참여자는 서버와 별도의 PeerConnection을 맺어 오디오를 전송하고,
    서버는 MediaRecorder로 webm 파일로 녹음합니다.
    """

    def __init__(self, meeting_id: UUID, user_id: UUID):
        self.meeting_id = meeting_id
        self.user_id = user_id
        self.pc: RTCPeerConnection | None = None
        self.recorder: MediaRecorder | None = None
        self.temp_file: str | None = None
        self.started_at: datetime | None = None
        self.recording_id: UUID | None = None
        self._track_received = asyncio.Event()

    async def setup(self) -> RTCPeerConnection:
        """PeerConnection 설정"""
        # ICE 서버 설정 (aiortc는 RTCConfiguration/RTCIceServer 객체 사용)
        ice_servers = []
        for server in ICE_SERVERS:
            urls = server["urls"]
            # urls가 문자열이면 리스트로 변환
            if isinstance(urls, str):
                urls = [urls]
            ice_servers.append(RTCIceServer(urls=urls))

        config = RTCConfiguration(iceServers=ice_servers)
        logger.info(f"[RecordingSession] Creating RTCPeerConnection with {len(ice_servers)} ICE servers")
        self.pc = RTCPeerConnection(configuration=config)

        # 임시 파일 생성
        fd, self.temp_file = tempfile.mkstemp(suffix=".webm")
        os.close(fd)

        # Track 수신 시 MediaRecorder 설정
        @self.pc.on("track")
        async def on_track(track):
            if track.kind == "audio":
                logger.info(f"[RecordingSession] Audio track received from user {self.user_id}")
                self.recorder = MediaRecorder(self.temp_file, format="webm")
                self.recorder.addTrack(track)
                await self.recorder.start()
                self.started_at = datetime.now(timezone.utc)
                self._track_received.set()

                # Track 종료 시 처리
                @track.on("ended")
                async def on_ended():
                    logger.info(f"[RecordingSession] Track ended for user {self.user_id}")

        # 연결 상태 로깅
        @self.pc.on("connectionstatechange")
        async def on_connection_state_change():
            logger.info(
                f"[RecordingSession] Connection state: {self.pc.connectionState} "
                f"for user {self.user_id}"
            )

        return self.pc

    async def handle_offer(self, sdp: dict) -> dict:
        """클라이언트 Offer 처리 및 Answer 반환

        Args:
            sdp: {"sdp": "...", "type": "offer"}

        Returns:
            Answer SDP: {"sdp": "...", "type": "answer"}
        """
        logger.info(f"[RecordingSession] Handling offer for user {self.user_id}")

        if not self.pc:
            logger.info(f"[RecordingSession] Setting up PeerConnection for user {self.user_id}")
            await self.setup()

        # SDP에서 값 추출
        sdp_str = sdp.get("sdp") if isinstance(sdp, dict) else None
        sdp_type = sdp.get("type") if isinstance(sdp, dict) else None

        if not sdp_str or not sdp_type:
            raise ValueError(f"Invalid SDP format: sdp={bool(sdp_str)}, type={sdp_type}")

        offer = RTCSessionDescription(sdp=sdp_str, type=sdp_type)
        logger.info(f"[RecordingSession] Setting remote description for user {self.user_id}")
        await self.pc.setRemoteDescription(offer)

        logger.info(f"[RecordingSession] Creating answer for user {self.user_id}")
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        # ICE gathering 완료 대기 (최대 5초)
        logger.info(f"[RecordingSession] Waiting for ICE gathering to complete...")
        await self._wait_for_ice_gathering(timeout=5.0)

        logger.info(f"[RecordingSession] Answer created for user {self.user_id}, "
                   f"ICE gathering state: {self.pc.iceGatheringState}")

        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type,
        }

    async def _wait_for_ice_gathering(self, timeout: float = 5.0) -> None:
        """ICE gathering 완료 대기

        Args:
            timeout: 최대 대기 시간 (초)
        """
        if not self.pc:
            return

        if self.pc.iceGatheringState == "complete":
            return

        gathering_complete = asyncio.Event()

        @self.pc.on("icegatheringstatechange")
        async def on_ice_gathering_state_change():
            logger.info(f"[RecordingSession] ICE gathering state: {self.pc.iceGatheringState}")
            if self.pc.iceGatheringState == "complete":
                gathering_complete.set()

        try:
            await asyncio.wait_for(gathering_complete.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[RecordingSession] ICE gathering timeout after {timeout}s, "
                          f"state: {self.pc.iceGatheringState}")

    async def handle_ice_candidate(self, candidate: dict) -> None:
        """ICE Candidate 추가

        Args:
            candidate: ICE candidate 객체 (브라우저 형식)
                {
                    "candidate": "candidate:... typ host ...",
                    "sdpMid": "0",
                    "sdpMLineIndex": 0
                }
        """
        if not self.pc or not candidate:
            return

        # candidate 문자열이 비어있으면 무시 (end-of-candidates)
        candidate_str = candidate.get("candidate", "")
        if not candidate_str:
            logger.debug(f"[RecordingSession] Empty candidate (end-of-candidates) for user {self.user_id}")
            return

        try:
            # 브라우저 candidate 문자열 파싱
            # 형식: "candidate:{foundation} {component} {protocol} {priority} {ip} {port} typ {type} ..."
            ice_candidate = self._parse_ice_candidate(candidate_str, candidate)
            if ice_candidate:
                await self.pc.addIceCandidate(ice_candidate)
                logger.debug(f"[RecordingSession] Added ICE candidate for user {self.user_id}")
        except Exception as e:
            logger.warning(f"[RecordingSession] Failed to add ICE candidate: {e}, candidate={candidate_str[:100]}")

    def _parse_ice_candidate(self, candidate_str: str, candidate_dict: dict):
        """브라우저 ICE candidate 문자열을 aiortc RTCIceCandidate로 파싱

        Args:
            candidate_str: "candidate:..." 형식의 문자열
            candidate_dict: sdpMid, sdpMLineIndex 포함 딕셔너리

        Returns:
            RTCIceCandidate 또는 None
        """
        from aiortc import RTCIceCandidate
        import re

        # "candidate:" 접두사 제거
        if candidate_str.startswith("candidate:"):
            candidate_str = candidate_str[10:]

        # 기본 필드 파싱: foundation component protocol priority ip port typ type
        parts = candidate_str.split()
        if len(parts) < 8:
            logger.warning(f"[RecordingSession] Invalid candidate format: {candidate_str[:50]}")
            return None

        try:
            foundation = parts[0]
            component = int(parts[1])
            protocol = parts[2].lower()
            priority = int(parts[3])
            ip = parts[4]
            port = int(parts[5])
            # parts[6]은 "typ"
            candidate_type = parts[7]

            # 선택적 필드 파싱 (raddr, rport 등)
            related_address = None
            related_port = None

            i = 8
            while i < len(parts) - 1:
                if parts[i] == "raddr":
                    related_address = parts[i + 1]
                    i += 2
                elif parts[i] == "rport":
                    related_port = int(parts[i + 1])
                    i += 2
                else:
                    i += 1

            return RTCIceCandidate(
                component=component,
                foundation=foundation,
                ip=ip,
                port=port,
                priority=priority,
                protocol=protocol,
                type=candidate_type,
                relatedAddress=related_address,
                relatedPort=related_port,
                sdpMid=candidate_dict.get("sdpMid"),
                sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
            )
        except (ValueError, IndexError) as e:
            logger.warning(f"[RecordingSession] Failed to parse candidate: {e}")
            return None

    async def stop_and_save(self, db: AsyncSession) -> MeetingRecording | None:
        """녹음 중지 및 MinIO 저장

        Args:
            db: 데이터베이스 세션

        Returns:
            저장된 MeetingRecording 또는 None
        """
        if not self.recorder or not self.temp_file:
            logger.warning(f"[RecordingSession] No recorder for user {self.user_id}")
            return None

        try:
            # 녹음 중지
            await self.recorder.stop()
            ended_at = datetime.now(timezone.utc)

            # 파일 크기 확인
            if not os.path.exists(self.temp_file):
                logger.warning(f"[RecordingSession] Temp file not found for user {self.user_id}")
                return None

            file_size = os.path.getsize(self.temp_file)
            if file_size == 0:
                logger.warning(f"[RecordingSession] Empty recording for user {self.user_id}")
                return None

            # MinIO 업로드
            timestamp = self.started_at.strftime("%Y%m%d_%H%M%S") if self.started_at else "unknown"
            file_path = storage_service.upload_recording_file(
                meeting_id=str(self.meeting_id),
                user_id=str(self.user_id),
                timestamp=timestamp,
                file_path=self.temp_file,
            )

            # DB 저장
            duration_ms = (
                int((ended_at - self.started_at).total_seconds() * 1000)
                if self.started_at
                else 0
            )
            recording = MeetingRecording(
                meeting_id=self.meeting_id,
                user_id=self.user_id,
                file_path=file_path,
                status=RecordingStatus.COMPLETED.value,
                started_at=self.started_at or ended_at,
                ended_at=ended_at,
                duration_ms=duration_ms,
                file_size_bytes=file_size,
            )
            db.add(recording)
            await db.commit()
            await db.refresh(recording)

            logger.info(
                f"[RecordingSession] Recording saved: {file_path} "
                f"({duration_ms}ms, {file_size} bytes)"
            )
            return recording

        except Exception as e:
            logger.error(f"[RecordingSession] Failed to save recording: {e}")
            raise
        finally:
            # 임시 파일 정리
            if self.temp_file and os.path.exists(self.temp_file):
                try:
                    os.unlink(self.temp_file)
                except Exception as e:
                    logger.warning(f"[RecordingSession] Failed to delete temp file: {e}")

    async def close(self) -> None:
        """리소스 정리"""
        if self.recorder:
            try:
                await self.recorder.stop()
            except Exception:
                pass
            self.recorder = None

        if self.pc:
            try:
                await self.pc.close()
            except Exception:
                pass
            self.pc = None

        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.unlink(self.temp_file)
            except Exception:
                pass
            self.temp_file = None


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

    async def handle_offer(self, user_id: UUID, sdp: dict) -> dict | None:
        """SDP Offer 처리 (Mesh 모드: 중계만)"""
        return None

    async def handle_answer(self, user_id: UUID, sdp: dict) -> None:
        """SDP Answer 처리 (Mesh 모드: 중계만)"""
        pass

    async def handle_ice_candidate(self, user_id: UUID, candidate: dict) -> None:
        """ICE Candidate 처리 (Mesh 모드: 중계만)"""
        pass

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
