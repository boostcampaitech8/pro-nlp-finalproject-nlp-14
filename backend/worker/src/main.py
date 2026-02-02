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
        self._agent_enabled = bool(
            self.config.agent_enabled and self.config.backend_api_url
        )
        self._tts_enabled = bool(self.config.tts_server_url)
        self._tts_client = TTSClient() if self._tts_enabled else None
        self._tts_queue: asyncio.Queue[str] | None = (
            asyncio.Queue(maxsize=50) if self._tts_enabled else None
        )
        self._tts_task: asyncio.Task | None = None
        self._tts_interrupt_event: asyncio.Event = asyncio.Event()
        # TTS 재생 중 플래그
        self._tts_playing: bool = False

        # 참여자별 STT 클라이언트 (user_id -> STTClient)
        self._stt_clients: dict[str, ClovaSpeechSTTClient] = {}

        # 참여자별 wake word 감지 플래그 (중간 결과에서 감지 시 True)
        self._wake_word_pending: dict[str, bool] = {}
        # context 선준비 작업 (wake word 감지 시 시작, 단일 task)
        self._context_prep_task: asyncio.Task | None = None
        # 현재 실행 중인 Agent 파이프라인 Task
        self._current_agent_task: asyncio.Task | None = None

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
        # wake word 플래그 정리
        self._wake_word_pending.pop(user_id, None)

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

        if event_type == "speech_start":
            # Wake word 기반 인터럽트로 변경됨
            # VAD speech_start에서는 인터럽트하지 않음
            logger.debug(f"VAD speech_start: user={user_id}")

        elif event_type == "speech_end":
            # STT에 발화 종료 알림
            if user_id in self._stt_clients:
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

        # 중간 결과 처리: wake word 감지
        if not segment.is_final:
            logger.debug(
                f"STT 중간 결과: [{participant_name}] text='{segment.text}'"
            )

            # 누적된 텍스트에서 wake word 감지
            if (
                self._agent_enabled
                and self.config.agent_wake_word in segment.text
                and not self._wake_word_pending.get(user_id, False)
            ):
                logger.info(
                    f"Wake word 조기 감지 (중간 결과): '{self.config.agent_wake_word}' "
                    f"in '{segment.text}'"
                )
                self._wake_word_pending[user_id] = True

                # Wake word 감지 즉시 TTS 인터럽트
                await self._cancel_current_agent()
                if self._tts_enabled:
                    self._tts_interrupt_event.set()
                    self._clear_tts_queue()
                logger.info(f"Wake word 인터럽트 발동: user={user_id}")

                # context 선준비 (pre_transcript_id 기준으로 업데이트)
                # 기존 task가 있으면 취소 후 새로 시작
                if self._pre_transcript_id:
                    if self._context_prep_task and not self._context_prep_task.done():
                        self._context_prep_task.cancel()
                    self._context_prep_task = asyncio.create_task(
                        self._prepare_context(self._pre_transcript_id)
                    )
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
            min_confidence=segment.min_confidence,
            agent_call=False,
        )

        response = await self.api_client.send_transcript_segment(request)
        if response:
            logger.debug(f"트랜스크립트 저장: id={response.id}")

        # wake word 처리: 중간 결과에서 이미 감지했거나 final에서 감지
        wake_word_triggered = self._wake_word_pending.pop(user_id, False)
        if not wake_word_triggered and self._agent_enabled:
            # final 결과에서도 wake word 확인 (중간 결과에서 놓친 경우)
            wake_word_triggered = self.config.agent_wake_word in segment.text

        if wake_word_triggered:
            logger.info(f"Wake word 최종 처리: '{segment.text}'")
            if response:
                # 기존 Agent 취소 (즉시 실행 + 취소 방식)
                await self._cancel_current_agent()
                # TTS만 재생 중인 경우도 인터럽트 (중간 결과에서 놓쳤을 때)
                if self._tts_enabled:
                    self._tts_interrupt_event.set()
                    self._clear_tts_queue()

                # 새 Agent 시작
                self._current_agent_task = asyncio.create_task(
                    self._run_agent_pipeline_with_prep(
                        response.id, self._pre_transcript_id
                    )
                )

        # preTranscriptId 최신화 (agent 파이프라인 태스크 생성 직후, 완료 전)
        if response:
            self._pre_transcript_id = response.id

    async def _cancel_current_agent(self) -> None:
        """현재 실행 중인 Agent 취소"""
        if self._current_agent_task and not self._current_agent_task.done():
            logger.info("기존 Agent 파이프라인 취소")
            self._current_agent_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._current_agent_task
            self._current_agent_task = None

            # TTS도 함께 정리
            self._tts_interrupt_event.set()
            self._clear_tts_queue()

    async def _prepare_context(self, pre_transcript_id: str) -> None:
        """Context 선준비 (wake word 조기 감지 시 호출)"""
        try:
            logger.info(f"Context 선준비 시작: pre_transcript_id={pre_transcript_id}")
            await self.api_client.update_agent_context(
                meeting_id=self.meeting_id,
                pre_transcript_id=pre_transcript_id,
            )
            logger.info("Context 선준비 완료")
        except Exception as e:
            logger.warning(f"Context 선준비 실패 (무시): {e}")

    async def _run_agent_pipeline_with_prep(
        self,
        transcript_id: str,
        pre_transcript_id: str | None,
    ) -> None:
        """Context 선준비 완료 후 Agent 파이프라인 실행"""
        try:
            # context 선준비 작업 완료 대기
            context_prepped = False
            if self._context_prep_task:
                try:
                    await self._context_prep_task
                    context_prepped = True
                except asyncio.CancelledError:
                    raise  # 취소는 상위로 전파
                except Exception:
                    pass  # 다른 에러는 무시하고 계속 진행
                self._context_prep_task = None

            # agent 파이프라인 실행 (선준비 성공 시에만 context skip)
            await self._run_agent_pipeline(
                transcript_id, pre_transcript_id, skip_context=context_prepped
            )
        except asyncio.CancelledError:
            logger.info("Agent 파이프라인 (with prep) 취소됨")
            raise

    async def _run_agent_pipeline(
        self,
        transcript_id: str,
        pre_transcript_id: str | None,
        skip_context: bool = False,
    ) -> None:
        """LLM 스트리밍 응답을 문장 단위로 채팅 전송

        Args:
            transcript_id: 현재 발화 transcript ID
            pre_transcript_id: 이전 transcript ID (context 조회 기준)
            skip_context: True면 context update 건너뜀 (선준비 완료 시)
        """
        logger.info(
            "Agent 파이프라인 시작: meeting_id=%s, transcript_id=%s, "
            "pre_transcript_id=%s, skip_context=%s",
            self.meeting_id,
            transcript_id,
            pre_transcript_id,
            skip_context,
        )

        # 새 Agent 응답 시작 전 인터럽트 이벤트 초기화
        # (wake word 발화로 인한 인터럽트가 새 응답에 영향주지 않도록)
        self._tts_interrupt_event.clear()

        try:
            # 1. Context update 호출 (선준비 안 된 경우만)
            if not skip_context and pre_transcript_id:
                await self.api_client.update_agent_context(
                    meeting_id=self.meeting_id,
                    pre_transcript_id=pre_transcript_id,
                )

            # 2. LLM 스트리밍 호출
            buffer = ""
            async for token in self.api_client.stream_agent_response(
                meeting_id=self.meeting_id,
                transcript_id=transcript_id,
            ):
                if not token:
                    continue

                buffer += token
                sentences, buffer = self._extract_sentences(buffer)
                for sentence in sentences:
                    await self.bot.send_chat_message(sentence)
                    self._enqueue_tts(sentence)

            tail = buffer.strip()
            if tail:
                await self.bot.send_chat_message(tail)
                self._enqueue_tts(tail)

        except asyncio.CancelledError:
            logger.info("Agent 파이프라인 취소됨")
            raise
        except Exception as e:
            logger.warning(f"Agent 스트리밍 실패: {e}")

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

            # 합성 전 인터럽트 체크 (큐에서 꺼낸 후 인터럽트 발생한 경우)
            if self._tts_interrupt_event.is_set():
                logger.info("TTS 합성 전 인터럽트 감지, 스킵: '%s...'", sentence[:30])
                self._tts_queue.task_done()
                continue

            try:
                audio_bytes = await self._tts_client.synthesize(sentence)
                if audio_bytes:
                    # 재생 직전 인터럽트 체크 (합성 중 인터럽트 발생한 경우)
                    if self._tts_interrupt_event.is_set():
                        logger.info("TTS 합성 후 인터럽트 감지, 재생 스킵")
                        self._tts_queue.task_done()
                        continue

                    # 재생 시작 직전에 이벤트 클리어 및 재생 중 플래그 설정
                    self._tts_interrupt_event.clear()
                    self._tts_playing = True
                    completed = await self.bot.play_pcm_bytes(
                        audio_bytes,
                        sample_rate=44100,
                        target_sample_rate=48000,
                        frame_duration_ms=20,
                        interrupt_event=self._tts_interrupt_event,
                    )
                    self._tts_playing = False  # 재생 완료/중단
                    if not completed:
                        # 중단됨 - 큐 비우기
                        logger.info("TTS 재생 중단됨, 큐 비우기")
                        self._clear_tts_queue()
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
                self._clear_tts_queue()
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

    def _clear_tts_queue(self) -> None:
        """TTS 큐 비우기 (대기 중인 문장 삭제)"""
        if not self._tts_queue:
            return
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
            except asyncio.QueueEmpty:
                break

    @staticmethod
    def _extract_sentences(text: str) -> tuple[list[str], str]:
        """마침표/종결부호 또는 줄바꿈 기준으로 문장 분리
        """
        if not text:
            return [], ""

        endings = {".", "!", "?", "。", "！", "？"}
        closing = {'"', "'", "\u201c", "\u201d", ")", "]", "}", "」", "』", "】"}

        sentences: list[str] = []
        start = 0
        i = 0

        while i < len(text):
            ch = text[i]

            # 줄바꿈도 문장 경계로 처리
            if ch == "\n":
                sentence = text[start:i].strip()
                if sentence:
                    sentences.append(sentence)
                start = i + 1
                i = start
                continue

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

    meeting_id = os.environ.get("MEETING_ID")

    if not meeting_id:
        logger.error("MEETING_ID 환경변수가 설정되지 않음")
        sys.exit(1)

    worker = RealtimeWorker(meeting_id)
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
