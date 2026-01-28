"""Realtime Worker 메인 진입점

현재: LiveKit 오디오 구독 → Clova Speech STT → Backend API 전송
향후: Backend RAG 응답 → TTS 변환 → LiveKit 오디오 발화
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

from src.clients.backend import BackendAPIClient, TranscriptSegmentRequest
from src.clients.stt import ClovaSpeechSTTClient, STTSegment
from src.config import get_config
from src.livekit import LiveKitBot

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class RealtimeWorker:
    """Realtime Worker

    현재 기능:
    1. LiveKit 회의에 Bot으로 참여
    2. 참여자 오디오를 구독
    3. Clova Speech STT로 실시간 변환
    4. 결과를 Backend API로 전송

    향후 기능:
    5. Backend에서 RAG 응답 수신
    6. TTS 변환 후 LiveKit으로 발화
    """

    def __init__(self, meeting_id: str):
        """
        Args:
            meeting_id: 회의 ID
        """
        self.meeting_id = meeting_id
        self.config = get_config()

        # 컴포넌트 초기화
        self.api_client = BackendAPIClient()

        # 참여자별 STT 클라이언트 (user_id -> STTClient)
        self._stt_clients: dict[str, ClovaSpeechSTTClient] = {}

        # LiveKit Bot
        self.bot = LiveKitBot(
            meeting_id=meeting_id,
            on_audio_frame=self._on_audio_frame,
            on_participant_joined=self._on_participant_joined,
            on_participant_left=self._on_participant_left,
            on_vad_event=self._on_vad_event,
        )

        self._is_running = False
        self._meeting_start_time: datetime | None = None

    async def start(self) -> None:
        """Worker 시작"""
        if self._is_running:
            logger.warning("Worker가 이미 실행 중")
            return

        logger.info(f"Realtime Worker 시작: meeting={self.meeting_id}")
        self._is_running = True
        self._meeting_start_time = datetime.now(timezone.utc)

        # API 클라이언트 연결
        await self.api_client.connect()

        # LiveKit 연결
        await self.bot.connect()

    async def stop(self) -> None:
        """Worker 종료"""
        if not self._is_running:
            return

        self._is_running = False

        # STT 클라이언트 종료
        for user_id, stt_client in self._stt_clients.items():
            await stt_client.stop_streaming()
            await stt_client.disconnect()
        self._stt_clients.clear()

        # LiveKit 연결 해제
        await self.bot.disconnect()

        # API 클라이언트 종료
        await self.api_client.disconnect()

        logger.info(f"Realtime Worker 종료: meeting={self.meeting_id}")

    async def run_forever(self) -> None:
        """무한 실행 (시그널 대기)"""
        await self.start()

        # 종료 시그널 대기
        stop_event = asyncio.Event()

        def signal_handler():
            logger.info("종료 시그널 수신")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        await stop_event.wait()
        await self.stop()

    def _on_participant_joined(self, user_id: str, participant_name: str) -> None:
        """참여자 입장 처리 - STT 클라이언트 생성"""
        if user_id in self._stt_clients:
            logger.warning(f"이미 STT 클라이언트가 존재: user={user_id}")
            return

        # 해당 참여자용 STT 클라이언트 생성
        stt_client = ClovaSpeechSTTClient(
            language="ko",
            on_result=lambda segment: asyncio.create_task(
                self._on_stt_result(user_id, participant_name, segment)
            ),
        )
        self._stt_clients[user_id] = stt_client

        # STT 스트리밍 시작
        asyncio.create_task(stt_client.start_streaming())

    def _on_participant_left(self, user_id: str) -> None:
        """참여자 퇴장 처리 - STT 클라이언트 종료"""
        if user_id not in self._stt_clients:
            return

        stt_client = self._stt_clients.pop(user_id)
        asyncio.create_task(stt_client.stop_streaming())
        asyncio.create_task(stt_client.disconnect())

    def _on_vad_event(self, user_id: str, event_type: str, payload: dict) -> None:
        """VAD 이벤트 수신 처리"""
        logger.info(
            f"VAD 이벤트: user={user_id}, type={event_type}, "
            f"start={payload.get('segmentStartMs')}, end={payload.get('segmentEndMs')}"
        )

        # speech_end 이벤트 시 STT에 발화 종료 알림
        if event_type == "speech_end" and user_id in self._stt_clients:
            stt_client = self._stt_clients[user_id]
            asyncio.create_task(stt_client.mark_end_of_speech())

    def _on_audio_frame(
        self,
        user_id: str,
        participant_name: str,
        pcm_data: bytes,
    ) -> None:
        """오디오 프레임 수신 - STT로 전달"""
        if user_id not in self._stt_clients:
            return

        stt_client = self._stt_clients[user_id]
        asyncio.create_task(stt_client.send_audio(pcm_data))

    async def _on_stt_result(
        self,
        user_id: str,
        participant_name: str,
        segment: STTSegment,
    ) -> None:
        """STT 결과 수신 - Backend API로 전송"""
        if not segment.text.strip():
            return

        # final 결과만 전송
        if not segment.is_final:
            logger.debug(f"STT 중간 결과: [{participant_name}] {segment.text}")
            return

        logger.info(
            f"STT 결과: [{participant_name}] '{segment.text}' "
            f"({segment.start_ms}~{segment.end_ms}ms, conf={segment.confidence:.2f})"
        )

        # Backend API로 전송
        request = TranscriptSegmentRequest(
            meeting_id=self.meeting_id,
            user_id=user_id,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
            confidence=segment.confidence,
            agent_call=False,
        )

        response = await self.api_client.send_transcript_segment(request)
        if response:
            logger.debug(f"트랜스크립트 저장: id={response.id}")


async def main():
    """메인 함수"""
    config = get_config()
    logger.setLevel(config.log_level)

    # 환경변수에서 meeting_id 가져오기
    import os

    meeting_id = os.environ.get("MEETING_ID", "meeting-1e62ab82-b35e-4010-86f3-44c9a1d30749")

    if not meeting_id:
        logger.error("MEETING_ID 환경변수가 설정되지 않음")
        sys.exit(1)

    worker = RealtimeWorker(meeting_id)
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
