"""OpenTelemetry 계측 설정

모든 컴포넌트(Backend, ARQ Worker)에서 공통으로 사용하는
OTel 초기화 로직을 제공합니다.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

T = TypeVar("T")


def init_telemetry(
    service_name: str,
    service_version: str = "0.1.0",
    otlp_endpoint: str | None = None,
) -> tuple[trace.Tracer, metrics.Meter]:
    """OpenTelemetry 초기화

    Args:
        service_name: 서비스 이름 (예: "mit-backend", "mit-arq-worker")
        service_version: 서비스 버전
        otlp_endpoint: OTLP 수신 엔드포인트 (기본값: OTEL_EXPORTER_OTLP_ENDPOINT 환경변수)

    Returns:
        (Tracer, Meter) 튜플
    """
    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4317")

    # Resource 설정 (서비스 메타데이터)
    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: service_version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv("APP_ENV", "development"),
        }
    )

    # Tracer Provider 설정
    # TODO: Tempo 설치 후 traces export 활성화
    # - Alloy configmap에서 traces output 추가 필요
    # - 현재는 Alloy가 traces receiver를 지원하지 않아 UNIMPLEMENTED 에러 발생
    tracer_provider = TracerProvider(resource=resource)
    # span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    # tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    # Meter Provider 설정
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=10000,  # 10초마다 export
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    tracer = trace.get_tracer(service_name, service_version)
    meter = metrics.get_meter(service_name, service_version)

    logger.info(
        "Telemetry initialized: service=%s, endpoint=%s",
        service_name,
        endpoint,
    )

    return tracer, meter


def instrument_fastapi(app: FastAPI) -> None:
    """FastAPI 자동 계측"""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument FastAPI: %s", e)


def instrument_common() -> None:
    """공통 라이브러리 자동 계측"""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument HTTPX: %s", e)

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
        logger.info("Redis instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument Redis: %s", e)


def instrument_sqlalchemy(engine: Engine) -> None:
    """SQLAlchemy 자동 계측"""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumentation enabled")
    except Exception as e:
        logger.warning("Failed to instrument SQLAlchemy: %s", e)


# ===========================================
# MIT 프로젝트 전용 메트릭
# ===========================================


class MITMetrics:
    """MIT 프로젝트 커스텀 메트릭"""

    def __init__(self, meter: metrics.Meter):
        self.meter = meter
        self._init_http_metrics()
        self._init_arq_metrics()
        self._init_realtime_metrics()
        self._init_k8s_metrics()

    def _init_http_metrics(self) -> None:
        """HTTP 요청 메트릭"""
        self.http_request_duration = self.meter.create_histogram(
            name="mit_http_request_duration_seconds",
            description="HTTP 요청 처리 시간",
            unit="s",
        )
        self.http_requests_total = self.meter.create_counter(
            name="mit_http_requests_total",
            description="총 HTTP 요청 수",
        )

    def _init_arq_metrics(self) -> None:
        """ARQ 태스크 메트릭"""
        self.arq_task_enqueue_total = self.meter.create_counter(
            name="mit_arq_task_enqueue_total",
            description="ARQ 태스크 enqueue 수",
        )
        self.arq_task_duration = self.meter.create_histogram(
            name="mit_arq_task_duration_seconds",
            description="ARQ 태스크 실행 시간",
            unit="s",
        )
        self.arq_task_result = self.meter.create_counter(
            name="mit_arq_task_result_total",
            description="ARQ 태스크 결과 (success/failed)",
        )
        self.arq_task_wait_duration = self.meter.create_histogram(
            name="mit_arq_task_wait_duration_seconds",
            description="ARQ 태스크 대기 시간 (enqueue → 실행 시작)",
            unit="s",
        )

    def _init_realtime_metrics(self) -> None:
        """Realtime Worker 파이프라인 메트릭 (Backend에서도 일부 사용)"""
        self.vad_to_stt_latency = self.meter.create_histogram(
            name="mit_vad_to_stt_latency_seconds",
            description="VAD speech_end → STT 결과 저장 레이턴시",
            unit="s",
        )
        self.wakeword_to_agent_latency = self.meter.create_histogram(
            name="mit_wakeword_to_agent_latency_seconds",
            description="Wake word 감지 → Agent 첫 토큰 출력 레이턴시",
            unit="s",
        )
        self.wakeword_to_tts_latency = self.meter.create_histogram(
            name="mit_wakeword_to_tts_latency_seconds",
            description="Wake word 감지 → TTS 첫 오디오 출력 레이턴시",
            unit="s",
        )
        self.stt_processing_duration = self.meter.create_histogram(
            name="mit_stt_processing_duration_seconds",
            description="STT 오디오 전송 → 결과 수신 시간",
            unit="s",
        )
        self.tts_synthesis_duration = self.meter.create_histogram(
            name="mit_tts_synthesis_duration_seconds",
            description="TTS 텍스트 → 오디오 합성 시간",
            unit="s",
        )

    def _init_k8s_metrics(self) -> None:
        """K8s Job 관련 메트릭"""
        self.webhook_to_job_latency = self.meter.create_histogram(
            name="mit_webhook_to_job_creation_seconds",
            description="LiveKit 웹훅 수신 → K8s Job 생성 완료 시간",
            unit="s",
        )
        self.realtime_worker_jobs_total = self.meter.create_counter(
            name="mit_realtime_worker_jobs_total",
            description="Realtime Worker Job 생성 수",
        )


# ===========================================
# 싱글톤 인스턴스 및 접근자
# ===========================================

_tracer: trace.Tracer | None = None
_meter: metrics.Meter | None = None
_mit_metrics: MITMetrics | None = None
_initialized: bool = False


def is_telemetry_initialized() -> bool:
    """Telemetry 초기화 여부 확인"""
    return _initialized


def get_tracer() -> trace.Tracer:
    """Tracer 인스턴스 반환 (초기화 안 된 경우 noop tracer 반환)"""
    global _tracer
    if _tracer is None:
        return trace.get_tracer("mit-noop")
    return _tracer


def get_meter() -> metrics.Meter:
    """Meter 인스턴스 반환 (초기화 안 된 경우 noop meter 반환)"""
    global _meter
    if _meter is None:
        return metrics.get_meter("mit-noop")
    return _meter


def get_mit_metrics() -> MITMetrics | None:
    """MIT 메트릭 인스턴스 반환 (초기화 안 된 경우 None)"""
    return _mit_metrics


def setup_telemetry(service_name: str, service_version: str = "0.1.0") -> None:
    """전역 telemetry 설정 (애플리케이션 시작 시 호출)"""
    global _tracer, _meter, _mit_metrics, _initialized

    if _initialized:
        logger.warning("Telemetry already initialized, skipping")
        return

    _tracer, _meter = init_telemetry(service_name, service_version)
    _mit_metrics = MITMetrics(_meter)
    instrument_common()
    _initialized = True


# ===========================================
# 유틸리티 데코레이터 및 컨텍스트 매니저
# ===========================================


def traced_function(
    span_name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """함수를 OTel span으로 래핑하는 데코레이터

    Usage:
        @traced_function("my_operation")
        async def my_func():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        name = span_name or func.__name__

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


@contextmanager
def timed_operation(metric_name: str, labels: dict[str, str] | None = None):
    """시간 측정 컨텍스트 매니저

    Usage:
        with timed_operation("my_operation", {"endpoint": "/api/v1/..."}) as timer:
            # do something
        # timer.duration에 경과 시간 저장됨
    """

    class Timer:
        def __init__(self):
            self.start_time = time.perf_counter()
            self.duration: float = 0.0

    timer = Timer()
    try:
        yield timer
    finally:
        timer.duration = time.perf_counter() - timer.start_time
        # 메트릭 기록은 호출자가 직접 처리
