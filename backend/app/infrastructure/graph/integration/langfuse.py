"""Langfuse LLM Observability 통합."""

from functools import lru_cache
import logging
from typing import Optional

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from opentelemetry.sdk.trace import TracerProvider

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_langfuse_base_url(settings) -> str:
    """Langfuse base URL 반환 (호환성 지원: langfuse_host → langfuse_base_url)"""
    return getattr(
        settings,
        "langfuse_base_url",
        getattr(settings, "langfuse_host", "https://cloud.langfuse.com"),
    )


def is_langfuse_enabled(settings) -> bool:
    """Langfuse 활성화 여부 반환 (호환성 지원: langfuse_enabled → langfuse_tracing_enabled)"""
    return bool(
        getattr(
            settings,
            "langfuse_tracing_enabled",
            getattr(settings, "langfuse_enabled", True),
        )
    )


@lru_cache(maxsize=1)
def _initialize_langfuse_client(
    public_key: str,
    secret_key: str,
    base_url: str,
) -> None:
    # 앱의 전역 OTel 트레이서와 분리된 Langfuse 전용 provider를 사용한다.
    # 이렇게 하면 FastAPI/Redis/HTTPX 자동계측 스팬이 Langfuse에 중복 수집되지 않는다.
    Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
        tracing_enabled=True,
        tracer_provider=TracerProvider(),
    )
    logger.info("Langfuse client initialized with isolated tracer provider.")


def get_runnable_config(
    trace_name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """LangGraph/LangChain 실행을 위한 config 반환.

    Langfuse 콜백이 포함된 config를 생성하여 전체 워크플로우 추적을 활성화합니다.
    최상위 ainvoke/astream 호출 시에만 사용하면 내부 호출에 자동 전파됩니다.

    Args:
        trace_name: Langfuse 트레이스 이름 (예: "mit_search", "generate_pr")
        user_id: 사용자 ID (Langfuse에서 사용자별 필터링용)
        session_id: 세션 ID (대화 세션 추적용)
        metadata: 추가 메타데이터

    Returns:
        LangGraph/LangChain의 ainvoke/invoke에 전달할 config dict

    Example:
        config = get_runnable_config(trace_name="mit_search", user_id="user-123")
        result = await graph.ainvoke(state, config=config)
    """
    settings = get_settings()

    if not is_langfuse_enabled(settings):
        logger.info("Langfuse tracing disabled by settings (LANGFUSE_TRACING_ENABLED=false).")
        return {}

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning(
            "Langfuse tracing disabled: missing LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY."
        )
        return {}

    base_url = get_langfuse_base_url(settings)
    _initialize_langfuse_client(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=base_url,
    )

    # CallbackHandler에 user_id, session_id 직접 전달 (Langfuse 대시보드 필터링 지원)
    callback_handler = CallbackHandler(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=base_url,
        user_id=user_id,
        session_id=session_id,
    )

    return {
        "callbacks": [callback_handler],
        **({"run_name": trace_name} if trace_name else {}),
        **({"metadata": metadata} if metadata else {}),
    }
