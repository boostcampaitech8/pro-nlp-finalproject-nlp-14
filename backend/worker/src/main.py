"""Realtime Worker 메인 진입점

현재: LiveKit 오디오 구독 -> Clova Speech STT -> Backend API 전송
      + ContextManager를 통한 컨텍스트 엔지니어링
향후: Backend RAG 응답 -> TTS 변환 -> LiveKit 오디오 발화
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# backend/app을 import 경로에 추가
BACKEND_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from src.clients.backend import BackendAPIClient, TranscriptSegmentRequest
from src.clients.stt import ClovaSpeechSTTClient, STTSegment
from src.config import get_config
from src.livekit import LiveKitBot

# Context Engineering 모듈 import
from app.infrastructure.context import (
    ContextBuilder,
    ContextConfig,
    ContextManager,
    Utterance,
    format_context_as_system_prompt,
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Context 전용 로거 (시각화용)
context_logger = logging.getLogger("context")
context_logger.setLevel(logging.INFO)


class RealtimeWorker:
    """Realtime Worker

    현재 기능:
    1. LiveKit 회의에 Bot으로 참여
    2. 참여자 오디오를 구독
    3. Clova Speech STT로 실시간 변환
    4. 결과를 Backend API로 전송
    5. ContextManager로 컨텍스트 관리 (L0/L1)

    향후 기능:
    6. Backend에서 RAG 응답 수신
    7. TTS 변환 후 LiveKit으로 발화
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

        # 참여자 정보 캐시 (user_id -> name)
        self._participant_names: dict[str, str] = {}

        # LiveKit Bot
        self.bot = LiveKitBot(
            meeting_id=meeting_id,
            on_audio_frame=self._on_audio_frame,
            on_participant_joined=self._on_participant_joined,
            on_participant_left=self._on_participant_left,
            on_vad_event=self._on_vad_event,
        )

        # Context Engineering
        context_config = ContextConfig(
            l0_max_turns=25,
            l1_topic_check_interval_turns=5,
            topic_quick_check_enabled=True,
        )
        self.context_manager = ContextManager(
            meeting_id=meeting_id,
            config=context_config,
        )
        self.context_builder = ContextBuilder()

        self._is_running = False
        self._meeting_start_time: datetime | None = None
        self._utterance_counter = 0

        # 컨텍스트 시각화 주기 (발화 N개마다 출력)
        self._context_viz_interval = 5

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

        # 컨텍스트 상태 복원 시도
        await self.context_manager.restore_from_db()

        # 컨텍스트 시각화 초기 출력
        self._print_context_status()

    async def stop(self) -> None:
        """Worker 종료"""
        if not self._is_running:
            return

        self._is_running = False

        # 최종 컨텍스트 상태 출력
        logger.info("=== 최종 컨텍스트 상태 ===")
        self._print_context_status()

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

        # 참여자 이름 캐시
        self._participant_names[user_id] = participant_name

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

        context_logger.info(f"[참여자 입장] {participant_name} ({user_id})")

    def _on_participant_left(self, user_id: str) -> None:
        """참여자 퇴장 처리 - STT 클라이언트 종료"""
        if user_id not in self._stt_clients:
            return

        participant_name = self._participant_names.get(user_id, user_id)
        context_logger.info(f"[참여자 퇴장] {participant_name} ({user_id})")

        stt_client = self._stt_clients.pop(user_id)
        asyncio.create_task(stt_client.stop_streaming())
        asyncio.create_task(stt_client.disconnect())

        # 참여자 이름 캐시 정리
        self._participant_names.pop(user_id, None)

    def _on_vad_event(self, user_id: str, event_type: str, payload: dict) -> None:
        """VAD 이벤트 수신 처리"""
        logger.debug(
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
        """STT 결과 수신 - Backend API로 전송 + ContextManager 업데이트"""
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

        # 발화 카운터 증가
        self._utterance_counter += 1

        # Utterance 객체 생성
        utterance = Utterance(
            id=self._utterance_counter,
            speaker_id=user_id,
            speaker_name=participant_name,
            text=segment.text,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            confidence=segment.confidence,
            absolute_timestamp=datetime.now(timezone.utc),
        )

        # ContextManager에 발화 추가
        await self.context_manager.add_utterance(utterance)

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

        # 주기적으로 컨텍스트 상태 시각화
        if self._utterance_counter % self._context_viz_interval == 0:
            self._print_context_status()

    def _print_context_status(self) -> None:
        """컨텍스트 상태 시각화 출력"""
        snapshot = self.context_manager.get_context_snapshot()

        context_logger.info("")
        context_logger.info("=" * 60)
        context_logger.info("           CONTEXT ENGINEERING STATUS")
        context_logger.info("=" * 60)

        # L0 상태
        context_logger.info("")
        context_logger.info("[L0 - Active Context] (Raw Window)")
        context_logger.info(f"  Current Topic: {snapshot['current_topic']}")
        context_logger.info(f"  Buffer Size: {snapshot['l0_buffer_size']} utterances")
        context_logger.info(f"  Topic Buffer Size: {snapshot['l0_topic_buffer_size']} utterances")

        # L0 최근 발화 표시
        recent = self.context_manager.get_l0_utterances(limit=5)
        if recent:
            context_logger.info("  Recent Utterances:")
            for u in recent:
                ts = u.absolute_timestamp.strftime("%H:%M:%S")
                text_preview = u.text[:40] + "..." if len(u.text) > 40 else u.text
                context_logger.info(f"    [{ts}] {u.speaker_name}: {text_preview}")

        # L1 상태
        context_logger.info("")
        context_logger.info("[L1 - Topic History] (Segmented Summaries)")
        context_logger.info(f"  Segments Count: {snapshot['l1_segments_count']}")
        context_logger.info(f"  Last L1 Update: {snapshot['last_l1_update']}")

        # L1 토픽 세그먼트 표시
        segments = self.context_manager.get_l1_segments()
        if segments:
            context_logger.info("  Topic Segments:")
            for seg in segments[-3:]:  # 최근 3개만
                context_logger.info(f"    - {seg.name}: {seg.summary[:50]}...")
                if seg.keywords:
                    context_logger.info(f"      Keywords: {', '.join(seg.keywords)}")

        # 화자 정보
        context_logger.info("")
        context_logger.info("[Speaker Context]")
        speakers = snapshot.get('speakers', [])
        if speakers:
            speaker_ctx = self.context_manager.speaker_context
            roles = speaker_ctx.infer_roles()
            for speaker_id in speakers:
                stats = speaker_ctx.get_speaker_stats(speaker_id)
                if stats:
                    role = roles.get(speaker_id, "participant")
                    context_logger.info(
                        f"  - {stats.name}: {stats.utterance_count} utterances, "
                        f"role={role}, q_ratio={stats.question_count}/{stats.utterance_count}"
                    )
        else:
            context_logger.info("  No speakers yet")

        context_logger.info("=" * 60)
        context_logger.info("")

    def get_context_for_agent(self, call_type: str = "IMMEDIATE_RESPONSE") -> str:
        """에이전트 호출용 컨텍스트 반환

        Args:
            call_type: 호출 유형

        Returns:
            str: 시스템 프롬프트 형태의 컨텍스트
        """
        context = self.context_builder.build_context(
            call_type=call_type,
            context_manager=self.context_manager,
        )
        return format_context_as_system_prompt(context)


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
