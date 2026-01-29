"""Realtime Worker 메인 진입점

현재: LiveKit 오디오 구독 → Clova Speech STT → Backend API 전송
향후: Backend RAG 응답 → TTS 변환 → LiveKit 오디오 발화
"""

import asyncio
import logging
import signal
import sys
from contextlib import suppress
from datetime import datetime, timezone

from src.clients.backend import BackendAPIClient, TranscriptSegmentRequest
from src.clients.stt import ClovaSpeechSTTClient, STTSegment
from src.clients.tts import TTSClient
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
        self._agent_lock = asyncio.Lock()
        self._agent_enabled = bool(
            self.config.agent_enabled and self.config.backend_api_url
        )
        self._tts_enabled = bool(self.config.tts_server_url)
        self._tts_client = TTSClient() if self._tts_enabled else None
        self._tts_queue: asyncio.Queue[str] | None = (
            asyncio.Queue(maxsize=50) if self._tts_enabled else None
        )
        self._tts_task: asyncio.Task | None = None

        # 참여자별 STT 클라이언트 (user_id -> STTClient)
        self._stt_clients: dict[str, ClovaSpeechSTTClient] = {}

        # LiveKit Bot
        self.bot = LiveKitBot(
            meeting_id=meeting_id,
            on_audio_frame=self._on_audio_frame,
            on_participant_joined=self._on_participant_joined,
            on_participant_left=self._on_participant_left,
            on_vad_event=self._on_vad_event,
            enable_tts_publish=self._tts_enabled,
        )

        self._is_running = False
        self._meeting_start_time: datetime | None = None

        # Agent 호출용 이전 transcript ID
        self._pre_transcript_id: str | None = None

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

        # TTS 루프 시작
        if self._tts_client:
            await self._tts_client.connect()
            self._tts_task = asyncio.create_task(self._tts_loop())
            logger.info("TTS 파이프라인 활성화: server=%s", self.config.tts_server_url)
        else:
            logger.info("TTS 비활성화 (TTS_SERVER_URL 미설정)")

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

        # TTS 루프 종료
        if self._tts_task:
            self._tts_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._tts_task
            self._tts_task = None

        if self._tts_client:
            await self._tts_client.disconnect()
            self._tts_client = None

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

        # wake word 감지 시에만 Agent 파이프라인 호출 (최신화 전에 호출)
        if self._agent_enabled and self.config.agent_wake_word in segment.text:
            logger.info(f"Wake word 감지: '{self.config.agent_wake_word}' in '{segment.text}'")
            if response:
                # pre_transcript_id를 인자로 전달 (asyncio.create_task 타이밍 문제 방지)
                asyncio.create_task(
                    self._run_agent_pipeline(response.id, self._pre_transcript_id)
                )

        # preTranscriptId 최신화 (agent 파이프라인 호출 후)
        if response:
            self._pre_transcript_id = response.id

    async def _run_agent_pipeline(
        self,
        transcript_id: str,
        pre_transcript_id: str | None,
    ) -> None:
        """LLM 스트리밍 응답을 문장 단위로 채팅 전송

        Args:
            transcript_id: 현재 발화 transcript ID
            pre_transcript_id: 이전 transcript ID (context 조회 기준)
        """
        async with self._agent_lock:
            logger.info(
                "Agent 파이프라인 시작: meeting_id=%s, transcript_id=%s, pre_transcript_id=%s",
                self.meeting_id,
                transcript_id,
                pre_transcript_id,
            )

            # 1. Context update 호출
            if pre_transcript_id:
                await self.api_client.update_agent_context(
                    meeting_id=self.meeting_id,
                    pre_transcript_id=pre_transcript_id,
                )

            # 2. LLM 스트리밍 호출
            buffer = ""
            try:
                async for token in self.api_client.stream_agent_response(
                    meeting_id=self.meeting_id,
                    transcript_id=transcript_id,
                ):
                    if not token:
                        continue

                    buffer += token
                    sentences, buffer = self._extract_sentences(buffer)
                    for sentence in sentences:
                        # await self.bot.send_chat_message(sentence)
                        self._enqueue_tts(sentence)

                tail = buffer.strip()
                if tail:
                    # await self.bot.send_chat_message(tail)
                    self._enqueue_tts(tail)

            except Exception as e:
                logger.warning(f"Agent 스트리밍 실패 (무시): {e}")

    async def _tts_loop(self) -> None:
        """TTS 큐를 처리해 LiveKit으로 오디오 전송"""
        if not self._tts_queue or not self._tts_client:
            return

        consecutive_failures = 0
        max_consecutive_failures = 5

        while True:
            try:
                sentence = await self._tts_queue.get()
            except asyncio.CancelledError:
                break

            try:
                audio_bytes = await self._tts_client.synthesize(sentence)
                if audio_bytes:
                    await self.bot.play_pcm_bytes(
                        audio_bytes,
                        sample_rate=44100,
                        target_sample_rate=48000,
                        frame_duration_ms=20,
                    )
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    logger.warning(
                        "TTS 합성 실패 (None 반환): text='%s...' [연속 실패: %d/%d]",
                        sentence[:30],
                        consecutive_failures,
                        max_consecutive_failures,
                    )
            except Exception as exc:
                consecutive_failures += 1
                logger.warning(
                    "TTS 재생 실패: %s [연속 실패: %d/%d]",
                    exc,
                    consecutive_failures,
                    max_consecutive_failures,
                    exc_info=True,
                )

            if consecutive_failures >= max_consecutive_failures:
                logger.error(
                    "TTS 연속 %d회 실패, 큐 비우기 (서버 상태 확인 필요)",
                    max_consecutive_failures,
                )
                while not self._tts_queue.empty():
                    try:
                        self._tts_queue.get_nowait()
                        self._tts_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                consecutive_failures = 0

            self._tts_queue.task_done()

    def _enqueue_tts(self, text: str) -> None:
        """문장을 TTS 큐에 적재"""
        if not self._tts_queue or not self._tts_client:
            return

        message = text.strip()
        if not message:
            return

        try:
            self._tts_queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("TTS 큐가 가득 참, 메시지 드랍: %s...", message[:50])

    @staticmethod
    def _extract_sentences(text: str) -> tuple[list[str], str]:
        """마침표/종결부호 기준으로 문장 분리"""
        if not text:
            return [], ""

        endings = {".", "!", "?", "。", "！", "？"}
        closing = {'"', "'", "”", "’", ")", "]", "}", "」", "』", "】"}

        sentences: list[str] = []
        start = 0
        i = 0

        while i < len(text):
            ch = text[i]
            if ch in endings:
                end = i + 1
                while end < len(text) and (text[end] in endings or text[end] in closing):
                    end += 1

                sentence = text[start:end].strip()
                if sentence:
                    sentences.append(sentence)
                start = end
                i = end
                continue

            i += 1

        return sentences, text[start:]


async def main():
    """메인 함수"""
    config = get_config()
    logger.setLevel(config.log_level)

    # 환경변수에서 meeting_id 가져오기
    import os

    meeting_id = os.environ.get("MEETING_ID", "meeting-1de53207-db52-43a7-b928-0a912155202f")

    if not meeting_id:
        logger.error("MEETING_ID 환경변수가 설정되지 않음")
        sys.exit(1)

    worker = RealtimeWorker(meeting_id)
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
