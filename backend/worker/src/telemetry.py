"""Realtime Worker용 Telemetry 모듈

VAD → STT → Backend 및 Wake word → Agent → TTS 파이프라인의
레이턴시를 측정하기 위한 메트릭과 타임스탬프 관리.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

logger = logging.getLogger(__name__)


@dataclass
class PipelineTimestamps:
    """파이프라인 레이턴시 측정용 타임스탬프

    각 사용자별로 독립적인 타임스탬프를 관리합니다.
    """
    # VAD → STT 파이프라인
    vad_speech_end_time: float | None = None
    stt_final_received_time: float | None = None

    # Wake word → TTS 파이프라인
    wakeword_detected_time: float | None = None
    agent_first_token_time: float | None = None
    tts_first_audio_time: float | None = None

    def reset_vad_stt(self) -> None:
        """VAD→STT 파이프라인 타임스탬프 리셋"""
        self.vad_speech_end_time = None
        self.stt_final_received_time = None

    def reset_wakeword_tts(self) -> None:
        """WakeWord→TTS 파이프라인 타임스탬프 리셋"""
        self.wakeword_detected_time = None
        self.agent_first_token_time = None
        self.tts_first_audio_time = None


class RealtimeWorkerMetrics:
    """Realtime Worker 전용 메트릭

    주요 레이턴시 측정:
    - VAD speech_end → STT final 결과 수신
    - Wake word 감지 → Agent 첫 토큰 출력
    - Wake word 감지 → TTS 첫 오디오 출력
    """

    def __init__(self, meter: metrics.Meter, meeting_id: str):
        self.meter = meter
        self.meeting_id = meeting_id
        self._timestamps: dict[str, PipelineTimestamps] = {}

        # VAD → STT 레이턴시
        self.vad_to_stt_latency = meter.create_histogram(
            name="mit_vad_to_stt_latency_seconds",
            description="VAD speech_end → STT final 결과 레이턴시",
            unit="s",
        )

        # Wake word → Agent 첫 토큰
        self.wakeword_to_agent_latency = meter.create_histogram(
            name="mit_wakeword_to_agent_latency_seconds",
            description="Wake word 감지 → Agent 첫 토큰 출력",
            unit="s",
        )

        # Wake word → TTS 첫 발화
        self.wakeword_to_tts_latency = meter.create_histogram(
            name="mit_wakeword_to_tts_latency_seconds",
            description="Wake word 감지 → TTS 첫 오디오 출력",
            unit="s",
        )

        # STT 처리 시간 (개별 세그먼트)
        self.stt_processing_duration = meter.create_histogram(
            name="mit_stt_processing_duration_seconds",
            description="STT 오디오 전송 시작 → 결과 수신",
            unit="s",
        )

        # TTS 합성 시간
        self.tts_synthesis_duration = meter.create_histogram(
            name="mit_tts_synthesis_duration_seconds",
            description="TTS 요청 → 오디오 응답 수신",
            unit="s",
        )

        # Agent 응답 생성 시간
        self.agent_response_duration = meter.create_histogram(
            name="mit_agent_response_duration_seconds",
            description="Agent 요청 → 전체 응답 완료",
            unit="s",
        )

        # STT 세그먼트 카운터
        self.stt_segment_count = meter.create_counter(
            name="mit_stt_segment_total",
            description="STT 최종 결과 세그먼트 수",
        )

    def get_timestamps(self, user_id: str) -> PipelineTimestamps:
        """사용자별 타임스탬프 가져오기 (없으면 생성)"""
        if user_id not in self._timestamps:
            self._timestamps[user_id] = PipelineTimestamps()
        return self._timestamps[user_id]

    # =========================================================================
    # VAD → STT 파이프라인 측정
    # =========================================================================

    def mark_vad_speech_end(self, user_id: str) -> None:
        """VAD speech_end 이벤트 시점 기록"""
        ts = self.get_timestamps(user_id)
        ts.vad_speech_end_time = time.perf_counter()

    def mark_stt_final_received(self, user_id: str) -> None:
        """STT final 결과 수신 시점 기록 및 레이턴시 계산"""
        ts = self.get_timestamps(user_id)
        ts.stt_final_received_time = time.perf_counter()

        if ts.vad_speech_end_time:
            latency = ts.stt_final_received_time - ts.vad_speech_end_time
            self.vad_to_stt_latency.record(
                latency,
                {"meeting_id": self.meeting_id, "user_id": user_id},
            )
            logger.debug(
                f"VAD→STT latency: {latency:.3f}s (user={user_id})"
            )
        ts.reset_vad_stt()

    # =========================================================================
    # Wake word → TTS 파이프라인 측정
    # =========================================================================

    def mark_wakeword_detected(self, user_id: str) -> None:
        """Wake word 감지 시점 기록"""
        ts = self.get_timestamps(user_id)
        ts.wakeword_detected_time = time.perf_counter()

    def mark_agent_first_token(self, user_id: str) -> None:
        """Agent 첫 토큰 출력 시점 기록 및 레이턴시 계산"""
        ts = self.get_timestamps(user_id)
        ts.agent_first_token_time = time.perf_counter()

        if ts.wakeword_detected_time:
            latency = ts.agent_first_token_time - ts.wakeword_detected_time
            self.wakeword_to_agent_latency.record(
                latency,
                {"meeting_id": self.meeting_id, "user_id": user_id},
            )
            logger.debug(
                f"WakeWord→Agent latency: {latency:.3f}s (user={user_id})"
            )

    def mark_tts_first_audio(self, user_id: str) -> None:
        """TTS 첫 오디오 출력 시점 기록 및 레이턴시 계산"""
        ts = self.get_timestamps(user_id)
        ts.tts_first_audio_time = time.perf_counter()

        if ts.wakeword_detected_time:
            latency = ts.tts_first_audio_time - ts.wakeword_detected_time
            self.wakeword_to_tts_latency.record(
                latency,
                {"meeting_id": self.meeting_id, "user_id": user_id},
            )
            logger.debug(
                f"WakeWord→TTS latency: {latency:.3f}s (user={user_id})"
            )
        ts.reset_wakeword_tts()

    # =========================================================================
    # 개별 처리 시간 측정
    # =========================================================================

    def record_stt_duration(self, duration: float, user_id: str) -> None:
        """STT 처리 시간 기록"""
        self.stt_processing_duration.record(
            duration,
            {"meeting_id": self.meeting_id, "user_id": user_id},
        )

    def record_tts_duration(self, duration: float) -> None:
        """TTS 합성 시간 기록"""
        self.tts_synthesis_duration.record(
            duration,
            {"meeting_id": self.meeting_id},
        )

    def record_agent_duration(self, duration: float) -> None:
        """Agent 응답 생성 시간 기록"""
        self.agent_response_duration.record(
            duration,
            {"meeting_id": self.meeting_id},
        )

    def increment_stt_segment(self, user_id: str) -> None:
        """STT 최종 결과 세그먼트 카운트 증가"""
        self.stt_segment_count.add(
            1,
            {"meeting_id": self.meeting_id, "user_id": user_id},
        )


# =============================================================================
# 싱글톤 인스턴스 및 초기화
# =============================================================================

_metrics: RealtimeWorkerMetrics | None = None
_tracer: trace.Tracer | None = None
_initialized: bool = False
_livekit_connect_time: float = 0.0  # LiveKit 연결 시간 (epoch seconds)


def init_realtime_telemetry(meeting_id: str) -> RealtimeWorkerMetrics:
    """Realtime Worker Telemetry 초기화

    Args:
        meeting_id: 현재 회의 ID (리소스 속성으로 추가됨)

    Returns:
        RealtimeWorkerMetrics 인스턴스
    """
    global _metrics, _tracer, _initialized

    if _initialized:
        logger.warning("Realtime telemetry already initialized")
        return _metrics  # type: ignore

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4317")

    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: "mit-realtime-worker",
        ResourceAttributes.SERVICE_VERSION: "0.1.0",
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv("APP_ENV", "development"),
        "meeting.id": meeting_id,
    })

    # Tracer 설정
    # TODO: Tempo 설치 후 traces export 활성화
    # - Alloy configmap에서 traces output 추가 필요
    # - 현재는 Alloy가 traces receiver를 지원하지 않아 UNIMPLEMENTED 에러 발생
    tracer_provider = TracerProvider(resource=resource)
    # tracer_provider.add_span_processor(
    #     BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    # )
    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer("mit-realtime-worker", "0.1.0")

    # Meter 설정
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=5000,  # 5초마다 export
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter("mit-realtime-worker", "0.1.0")

    _metrics = RealtimeWorkerMetrics(meter, meeting_id)
    _initialized = True

    logger.info(
        f"Realtime telemetry initialized: meeting={meeting_id}, endpoint={endpoint}"
    )

    return _metrics


def get_realtime_metrics() -> RealtimeWorkerMetrics | None:
    """Realtime Worker 메트릭 인스턴스 반환"""
    return _metrics


def get_realtime_tracer() -> trace.Tracer:
    """Realtime Worker Tracer 인스턴스 반환"""
    global _tracer
    if _tracer is None:
        return trace.get_tracer("mit-realtime-worker-noop")
    return _tracer


def is_telemetry_initialized() -> bool:
    """Telemetry 초기화 여부 확인"""
    return _initialized


def set_livekit_connect_time() -> None:
    """LiveKit 연결 시간 기록 (STT 타임스탬프 기준점)"""
    global _livekit_connect_time
    _livekit_connect_time = time.time()
    logger.info(f"LiveKit connect time recorded: {_livekit_connect_time}")


def get_livekit_connect_time() -> float:
    """LiveKit 연결 시간 반환 (epoch seconds)"""
    return _livekit_connect_time
