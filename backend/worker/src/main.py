"""Realtime Worker 메인 진입점 (OTel 계측 포함)

현재: LiveKit 오디오 구독 → Clova Speech STT → Backend API 전송
향후: Backend RAG 응답 → TTS 변환 → LiveKit 오디오 발화

메트릭 측정:
- VAD speech_end → STT final 결과 레이턴시
- Wake word 감지 → Agent 첫 토큰 레이턴시
- Wake word 감지 → TTS 첫 발화 레이턴시
"""

import asyncio
import logging
import signal
import sys
import time
from contextlib import suppress
from datetime import datetime, timezone

from src.clients.backend import BackendAPIClient, TranscriptSegmentRequest
from src.clients.stt import ClovaSpeechSTTClient, STTSegment
from src.clients.tts import TTSClient
from src.config import get_config
from src.livekit import LiveKitBot
from src.utils.tts_normalize import normalize_tts_text
from src.telemetry import (
    RealtimeWorkerMetrics,
    get_realtime_metrics,
    init_realtime_telemetry,
    set_livekit_connect_time,
)

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

        # Telemetry 초기화
        self._metrics: RealtimeWorkerMetrics | None = init_realtime_telemetry(meeting_id)
        # Wake word 감지 사용자 추적 (레이턴시 측정용)
        self._wakeword_user_id: str | None = None
        # Agent 첫 토큰 기록 여부
        self._agent_first_token_recorded: bool = False
        # TTS 첫 발화 기록 여부
        self._tts_first_audio_recorded: bool = False

        # 컴포넌트 초기화
        self.api_client = BackendAPIClient()
        self._agent_enabled = bool(self.config.agent_enabled and self.config.backend_api_url)
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
        # 참여자별 wake word 감지 시 confidence 저장
        self._wake_word_confidence: dict[str, float] = {}
        # context 선준비 작업 (wake word 감지 시 시작, 단일 task)
        self._context_prep_task: asyncio.Task | None = None
        # 발화별 context 업데이트 작업 (단일 task)
        self._context_update_task: asyncio.Task | None = None
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
        self._stop_event = asyncio.Event()
        self._meeting_start_time: datetime | None = None

        # 회의 완료 태스크 (재입장 시 취소 가능)
        self._complete_task: asyncio.Task | None = None

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
        set_livekit_connect_time()  # STT 타임스탬프 기준점 기록

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
        """무한 실행 (시그널 또는 완료 이벤트 대기)"""
        await self.start()

        def signal_handler():
            logger.info("종료 시그널 수신")
            self._stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        await self._stop_event.wait()
        await self.stop()

    def _on_participant_joined(self, user_id: str, participant_name: str) -> None:
        """참여자 입장 처리 - STT 클라이언트 생성"""
        # 재입장 시 pending 회의 완료 취소
        if self._complete_task and not self._complete_task.done():
            logger.info(f"참여자 재입장, 회의 완료 취소: user={user_id}")
            self._complete_task.cancel()
            self._complete_task = None

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
        # wake word 플래그/confidence 정리
        self._wake_word_pending.pop(user_id, None)
        self._wake_word_confidence.pop(user_id, None)

        if user_id not in self._stt_clients:
            return

        stt_client = self._stt_clients.pop(user_id)
        asyncio.create_task(stt_client.stop_streaming())
        asyncio.create_task(stt_client.disconnect())

        # 모든 일반 참여자가 퇴장했는지 확인
        if self._all_real_participants_left():
            self._complete_task = asyncio.create_task(self._complete_meeting())

    def _all_real_participants_left(self) -> bool:
        """모든 일반 참여자가 퇴장했는지 확인 (Bot 제외)

        Bot은 _stt_clients에 포함되지 않으므로 자동 제외됨
        """
        return len(self._stt_clients) == 0

    async def _complete_meeting(self) -> None:
        """회의 완료 처리: 재입장 대기(5초) → POST /complete → graceful shutdown

        5초 grace period 동안 참여자가 재입장하면 태스크가 취소되어
        회의 완료/PR 생성/Job 삭제가 실행되지 않습니다.
        """
        try:
            # 1) 재입장 대기 겸 transcript flush (5초)
            logger.info("재입장 대기 및 transcript 플러시 (5초)...")
            await asyncio.sleep(5)

            # 2) 5초 후 재확인: 참여자가 다시 들어왔으면 중단
            if not self._all_real_participants_left():
                logger.info("참여자 재입장 감지, 회의 완료 중단")
                return

            # 3) Backend에 회의 완료 요청
            success = await self.api_client.complete_meeting(self.meeting_id)
            if success:
                logger.info("Meeting completed successfully by worker")
            else:
                logger.error("Failed to complete meeting")
        except asyncio.CancelledError:
            logger.info("회의 완료 취소됨 (참여자 재입장)")
            return
        except Exception as e:
            logger.exception(f"Error completing meeting: {e}")

        # 4) 성공/실패 무관하게 graceful shutdown 트리거
        #    run_forever() → self.stop() → bot.disconnect() → process exit
        logger.info("Graceful shutdown 시작")
        self._stop_event.set()

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
            # VAD speech_end 타임스탬프 기록
            if self._metrics:
                self._metrics.mark_vad_speech_end(user_id)

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
            logger.debug(f"STT 중간 결과: [{participant_name}] text='{segment.text}'")

            # 누적된 텍스트에서 wake word 감지
            if (
                self._agent_enabled
                and self.config.agent_wake_word in segment.text
                and not self._wake_word_pending.get(user_id, False)
            ):
                logger.info(
                    f"Wake word 조기 감지 (중간 결과): '{self.config.agent_wake_word}' "
                    f"in '{segment.text}', confidence={segment.confidence:.3f}"
                )
                self._wake_word_pending[user_id] = True
                self._wake_word_confidence[user_id] = segment.confidence

                # Wake word 감지 즉시 TTS 인터럽트
                await self._cancel_current_agent()
                if self._tts_enabled:
                    self._tts_interrupt_event.set()
                    self._clear_tts_queue()
                logger.info(f"Wake word 인터럽트 발동: user={user_id}")

                # 프론트에 listening 상태 전송
                await self.bot.send_agent_state("listening")

                # Wake word 감지 타임스탬프 기록
                if self._metrics:
                    self._metrics.mark_wakeword_detected(user_id)
                    self._wakeword_user_id = user_id
                    self._agent_first_token_recorded = False
                    self._tts_first_audio_recorded = False

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

        # STT final 결과 수신 타임스탬프 기록 (VAD→STT 레이턴시) + 세그먼트 카운트
        if self._metrics:
            self._metrics.mark_stt_final_received(user_id)
            self._metrics.increment_stt_segment(user_id)

        # wake word 처리: 중간 결과에서 이미 감지했거나 final에서 감지
        wake_word_triggered = self._wake_word_pending.pop(user_id, False)
        wake_word_confidence = self._wake_word_confidence.pop(user_id, None)

        if not wake_word_triggered and self._agent_enabled:
            # final 결과에서도 wake word 확인 (중간 결과에서 놓친 경우)
            if self.config.agent_wake_word in segment.text:
                wake_word_triggered = True
                wake_word_confidence = segment.confidence  # final에서 감지된 경우
                # final에서 감지한 경우에도 타임스탬프 기록
                if self._metrics:
                    self._metrics.mark_wakeword_detected(user_id)
                    self._wakeword_user_id = user_id
                    self._agent_first_token_recorded = False
                    self._tts_first_audio_recorded = False

        # Backend API로 전송
        request = TranscriptSegmentRequest(
            meeting_id=self.meeting_id,
            user_id=user_id,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
            confidence=segment.confidence,
            min_confidence=segment.min_confidence,
            agent_call=wake_word_triggered,
            agent_call_keyword=self.config.agent_wake_word if wake_word_triggered else None,
            agent_call_confidence=wake_word_confidence,
        )

        response = await self.api_client.send_transcript_segment(request)
        if response:
            logger.debug(f"트랜스크립트 저장: id={response.id}")
            # 발화 저장 직후 Context 업데이트 (실시간)
            if self._agent_enabled:
                if self._context_update_task and not self._context_update_task.done():
                    self._context_update_task.cancel()
                self._context_update_task = asyncio.create_task(
                    self._update_context_realtime(response.id)
                )

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
                    self._run_agent_pipeline_with_prep(response.id, self._pre_transcript_id)
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

    async def _update_context_realtime(self, transcript_id: str) -> None:
        """발화 저장 직후 Context 업데이트 (실시간)"""
        try:
            await self.api_client.update_agent_context(
                meeting_id=self.meeting_id,
                pre_transcript_id=transcript_id,
            )
        except Exception as e:
            logger.debug(f"Context 실시간 업데이트 실패 (무시): {e}")

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

        # 프론트에 thinking 상태 전송
        await self.bot.send_agent_state("thinking")

        try:
            # 1. Context update 호출 (선준비 안 된 경우만)
            if not skip_context and pre_transcript_id:
                await self.api_client.update_agent_context(
                    meeting_id=self.meeting_id,
                    pre_transcript_id=pre_transcript_id,
                )

            # 2. LLM 스트리밍 호출 (Planner → Tools → Generator)
            buffer = ""
            event_count = 0

            async for event in self.api_client.stream_agent_response(
                meeting_id=self.meeting_id,
                transcript_id=transcript_id,
            ):
                event_count += 1
                event_type = event.get("type")
                content = event.get("content", "")
                logger.info(f"[EVENT #{event_count}] type={event_type}")

                # ===== 상태 메시지: 프로필 위 텍스트로 표시 =====
                if event_type == "status":
                    if content:
                        logger.info(f"[STATUS] {content}")
                        await self.bot.send_agent_status(content)
                    continue

                # ===== 최종 답변: TTS + 채팅 =====
                if event_type == "message":
                    # Agent 첫 토큰 시점 기록 + speaking 상태 전송
                    if (
                        not self._agent_first_token_recorded
                        and self._metrics
                        and self._wakeword_user_id
                    ):
                        self._metrics.mark_agent_first_token(self._wakeword_user_id)
                        self._agent_first_token_recorded = True
                        await self.bot.send_agent_state("speaking")

                    if content:
                        logger.debug(f"[MESSAGE] len={len(content)}")
                        buffer += content
                        sentences, buffer = self._extract_sentences(buffer)
                        for sentence in sentences:
                            logger.info(f"[CHAT SEND] {sentence[:50]}...")
                            await self.bot.send_chat_message(sentence)
                            self._enqueue_tts(sentence)
                    continue

                # ===== 완료/에러 =====
                if event_type == "done":
                    logger.info("[SSE] Stream done")
                    break
                
                if event_type == "error":
                    logger.error(f"[SSE ERROR] {content}")
                    break
                # ===== 기타: 내부 이벤트는 무시 =====
                logger.debug(f"[SKIP] 미처리 이벤트: type={event_type} tag={tag}")

            # 남은 텍스트 처리
            tail = buffer.strip()
            if tail:
                logger.info(f"[CHAT SEND] 남은텍스트: {tail}")
                await self.bot.send_chat_message(tail)
                self._enqueue_tts(tail)

            # Agent 전체 응답 시간 기록
            if self._metrics:
                agent_duration = time.perf_counter() - agent_start_time
                self._metrics.record_agent_duration(agent_duration)

        except asyncio.CancelledError:
            logger.info("Agent 파이프라인 취소됨")
            raise
        except Exception as e:
            logger.warning(f"Agent 스트리밍 실패: {e}")
        finally:
            # 파이프라인 완료/취소/에러 시 idle 상태 전송
            await self.bot.send_agent_state("idle")

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
                tts_start_time = time.perf_counter()
                audio_bytes = await self._tts_client.synthesize(sentence)
                if audio_bytes:
                    # TTS 합성 시간 기록
                    if self._metrics:
                        tts_duration = time.perf_counter() - tts_start_time
                        self._metrics.record_tts_duration(tts_duration)

                    # 재생 직전 인터럽트 체크 (합성 중 인터럽트 발생한 경우)
                    if self._tts_interrupt_event.is_set():
                        logger.info("TTS 합성 후 인터럽트 감지, 재생 스킵")
                        self._tts_queue.task_done()
                        continue

                    # TTS 첫 발화 시점 기록 (WakeWord→TTS 레이턴시)
                    if (
                        not self._tts_first_audio_recorded
                        and self._metrics
                        and self._wakeword_user_id
                    ):
                        self._metrics.mark_tts_first_audio(self._wakeword_user_id)
                        self._tts_first_audio_recorded = True
                        self._wakeword_user_id = None  # 초기화

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

        message = normalize_tts_text(text)
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
        """마침표/종결부호 또는 줄바꿈 기준으로 문장 분리"""
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

