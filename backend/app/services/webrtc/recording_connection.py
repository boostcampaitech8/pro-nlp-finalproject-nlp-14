"""WebRTC 녹음 연결 관리 - RecordingSession의 연결 책임 분리"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder

from app.core.webrtc_config import ICE_SERVERS
from app.utils.ice_parser import ICECandidateParser

logger = logging.getLogger(__name__)


class WebRTCRecordingConnection:
    """WebRTC PeerConnection 관리 및 미디어 녹음

    RecordingSession의 WebRTC 연결 관리 책임을 분리한 클래스.
    RTCPeerConnection 설정, SDP offer/answer, ICE candidate 처리를 담당.
    """

    def __init__(self, meeting_id: UUID, user_id: UUID):
        """
        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
        """
        self.meeting_id = meeting_id
        self.user_id = user_id
        self.pc: RTCPeerConnection | None = None
        self.recorder: MediaRecorder | None = None
        self.temp_file: str | None = None
        self.started_at: datetime | None = None
        self._track_received = asyncio.Event()

    async def setup(self) -> RTCPeerConnection:
        """RTCPeerConnection 설정 및 초기화

        ICE 서버 설정, PeerConnection 생성, 이벤트 핸들러 등록을 수행.

        Returns:
            설정된 RTCPeerConnection 인스턴스
        """
        # ICE 서버 설정
        ice_servers = []
        for server in ICE_SERVERS:
            urls = server["urls"]
            if isinstance(urls, str):
                urls = [urls]
            ice_servers.append(RTCIceServer(urls=urls))

        config = RTCConfiguration(iceServers=ice_servers)
        logger.info(f"[WebRTCRecordingConnection] Creating RTCPeerConnection with {len(ice_servers)} ICE servers")
        self.pc = RTCPeerConnection(configuration=config)

        # 임시 파일 생성
        fd, self.temp_file = tempfile.mkstemp(suffix=".webm")
        os.close(fd)

        # Track 수신 시 MediaRecorder 설정
        @self.pc.on("track")
        async def on_track(track):
            if track.kind == "audio":
                logger.info(f"[WebRTCRecordingConnection] Audio track received from user {self.user_id}")
                self.recorder = MediaRecorder(self.temp_file, format="webm")
                self.recorder.addTrack(track)
                await self.recorder.start()
                self.started_at = datetime.now(timezone.utc)
                self._track_received.set()

                @track.on("ended")
                async def on_ended():
                    logger.info(f"[WebRTCRecordingConnection] Track ended for user {self.user_id}")

        # 연결 상태 로깅
        @self.pc.on("connectionstatechange")
        async def on_connection_state_change():
            logger.info(
                f"[WebRTCRecordingConnection] Connection state: {self.pc.connectionState} "
                f"for user {self.user_id}"
            )

        return self.pc

    async def handle_offer(self, sdp: dict) -> dict:
        """클라이언트 Offer 처리 및 Answer 반환

        Args:
            sdp: SDP Offer 딕셔너리 {"sdp": "...", "type": "offer"}

        Returns:
            SDP Answer 딕셔너리 {"sdp": "...", "type": "answer"}

        Raises:
            ValueError: SDP 형식이 잘못된 경우
        """
        logger.info(f"[WebRTCRecordingConnection] Handling offer for user {self.user_id}")

        if not self.pc:
            logger.info(f"[WebRTCRecordingConnection] Setting up PeerConnection for user {self.user_id}")
            await self.setup()

        # SDP 추출
        sdp_str = sdp.get("sdp") if isinstance(sdp, dict) else None
        sdp_type = sdp.get("type") if isinstance(sdp, dict) else None

        if not sdp_str or not sdp_type:
            raise ValueError(f"Invalid SDP format: sdp={bool(sdp_str)}, type={sdp_type}")

        # Offer 처리
        offer = RTCSessionDescription(sdp=sdp_str, type=sdp_type)
        logger.info(f"[WebRTCRecordingConnection] Setting remote description for user {self.user_id}")
        await self.pc.setRemoteDescription(offer)

        # Answer 생성
        logger.info(f"[WebRTCRecordingConnection] Creating answer for user {self.user_id}")
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        # ICE gathering 완료 대기
        logger.info(f"[WebRTCRecordingConnection] Waiting for ICE gathering to complete...")
        await self._wait_for_ice_gathering(timeout=5.0)

        logger.info(
            f"[WebRTCRecordingConnection] Answer created for user {self.user_id}, "
            f"ICE gathering state: {self.pc.iceGatheringState}"
        )

        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type,
        }

    async def add_ice_candidate(self, candidate: dict) -> None:
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

        # 빈 candidate 문자열은 무시 (end-of-candidates)
        candidate_str = candidate.get("candidate", "")
        if not candidate_str:
            logger.debug(f"[WebRTCRecordingConnection] Empty candidate (end-of-candidates) for user {self.user_id}")
            return

        try:
            ice_candidate = ICECandidateParser.parse(candidate_str, candidate)
            if ice_candidate:
                await self.pc.addIceCandidate(ice_candidate)
                logger.debug(f"[WebRTCRecordingConnection] Added ICE candidate for user {self.user_id}")
        except Exception as e:
            logger.warning(
                f"[WebRTCRecordingConnection] Failed to add ICE candidate: {e}, "
                f"candidate={candidate_str[:100]}"
            )

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
            logger.info(f"[WebRTCRecordingConnection] ICE gathering state: {self.pc.iceGatheringState}")
            if self.pc.iceGatheringState == "complete":
                gathering_complete.set()

        try:
            await asyncio.wait_for(gathering_complete.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"[WebRTCRecordingConnection] ICE gathering timeout after {timeout}s, "
                f"state: {self.pc.iceGatheringState}"
            )

    async def stop_recorder(self) -> datetime | None:
        """MediaRecorder 중지 및 종료 시각 반환

        Returns:
            녹음 종료 시각 또는 None (녹음이 없는 경우)
        """
        if not self.recorder:
            logger.warning(f"[WebRTCRecordingConnection] No recorder for user {self.user_id}")
            return None

        await self.recorder.stop()
        ended_at = datetime.now(timezone.utc)
        logger.info(f"[WebRTCRecordingConnection] Recorder stopped for user {self.user_id}")
        return ended_at

    async def close(self) -> None:
        """리소스 정리 (PeerConnection, MediaRecorder, 임시 파일)"""
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

    def get_temp_file_path(self) -> str | None:
        """임시 파일 경로 반환

        Returns:
            임시 파일 경로 또는 None
        """
        return self.temp_file

    def get_started_at(self) -> datetime | None:
        """녹음 시작 시각 반환

        Returns:
            녹음 시작 시각 또는 None
        """
        return self.started_at
