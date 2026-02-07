"""Langfuse LLM Observability 통합."""

from functools import lru_cache
import logging
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler
from opentelemetry.sdk.trace import TracerProvider

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CustomizedCallbackHandler(CallbackHandler):
    """Langfuse trace I/O를 커스터마이징하여 불필요한 state 필드 제외.

    LangGraph의 전체 state 대신 다음만 캡처:
    - Input: {"user_message": <사용자 입력 텍스트>}
    - Output: {"assistant_response": <최종 응답>}
    """

    def __init__(
        self,
        input_extractor: Optional[Callable[[Dict[str, Any]], Any]] = None,
        output_extractor: Optional[Callable[[Dict[str, Any]], Any]] = None,
        **kwargs
    ):
        """커스텀 extractor와 함께 초기화.

        Args:
            input_extractor: State에서 input 추출 함수
            output_extractor: 결과에서 output 추출 함수
            **kwargs: 부모 CallbackHandler에 전달
        """
        super().__init__(**kwargs)
        self.input_extractor = input_extractor or self._default_input_extractor
        self.output_extractor = output_extractor or self._default_output_extractor
        # Input을 저장하기 위한 딕셔너리 (run_id -> extracted_input)
        self._inputs_cache: Dict[UUID, Any] = {}

    @staticmethod
    def _default_input_extractor(state: Dict[str, Any]) -> Any:
        """LangGraph state에서 사용자 메시지 추출 (voice/spotlight 호환)."""
        if not isinstance(state, dict):
            return state

        # messages 리스트에서 추출 (LangGraph 표준)
        if "messages" in state and state["messages"]:
            first_msg = state["messages"][0]
            if hasattr(first_msg, "content"):
                return first_msg.content  # 문자열만 반환
            elif isinstance(first_msg, dict) and "content" in first_msg:
                return first_msg["content"]  # 문자열만 반환

        # Fallback: 직접 필드
        if "user_input" in state:
            return state["user_input"]  # 문자열만 반환

        # 최후: 전체 state 반환
        return state

    @staticmethod
    def _default_output_extractor(output: Dict[str, Any]) -> Any:
        """Chain output에서 assistant 응답 추출."""
        if not isinstance(output, dict):
            return output

        # 일반적인 응답 필드명 시도 (우선순위 순)
        for field in ["response", "output", "text", "answer"]:
            if field in output:
                return output[field]  # 문자열만 반환

        # Fallback: 전체 output
        return output

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> Any:
        """Input 커스터마이징을 위한 오버라이드."""
        # Input 추출 및 캐싱
        extracted_input = self.input_extractor(inputs)
        self._inputs_cache[run_id] = extracted_input

        # 부모 클래스의 on_chain_start 호출 (추출된 input으로 대체)
        return super().on_chain_start(
            serialized,
            extracted_input,
            run_id=run_id,
            parent_run_id=parent_run_id,
            **kwargs,
        )

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> Any:
        """커스텀 output 추출 적용을 위한 오버라이드."""
        try:
            # Output 추출
            extracted_output = self.output_extractor(outputs)

            # 캐시된 input 가져오기 (on_chain_start에서 저장됨)
            extracted_input = self._inputs_cache.get(run_id)

            # 부모 클래스의 on_chain_end 호출 (추출된 output으로)
            # 하지만 부모가 자동으로 trace를 업데이트하므로, 우리가 직접 처리
            span = self._detach_observation(run_id)

            if span is not None:
                # Span에 기록
                span.update(output=extracted_output)

                # Trace에 기록 (root span만)
                if parent_run_id is None and self.update_trace:
                    span.update_trace(
                        output=extracted_output,
                        input=extracted_input,  # 캐시된 input 사용
                    )

                span.end()
                self._deregister_langfuse_prompt(run_id)

            # 캐시 정리
            self._inputs_cache.pop(run_id, None)

        except Exception as e:
            from langfuse.logger import langfuse_logger
            langfuse_logger.exception(e)

        finally:
            if parent_run_id is None:
                self._reset()


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
    mode: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """LangGraph/LangChain 실행을 위한 config 반환.

    Langfuse 콜백이 포함된 config를 생성하여 전체 워크플로우 추적을 활성화합니다.
    최상위 ainvoke/astream 호출 시에만 사용하면 내부 호출에 자동 전파됩니다.

    Args:
        trace_name: Langfuse 트레이스 이름 (예: "mit_search", "generate_pr")
        user_id: 사용자 ID (Langfuse에서 사용자별 필터링용)
        session_id: 세션 ID (대화 세션 추적용)
        mode: 오케스트레이션 모드 (예: "voice", "spotlight") - Langfuse에서 모드별 필터링용
        metadata: 추가 메타데이터
        tags: Langfuse UI 필터링용 태그 (예: ["voice", "dev"], ["spotlight", "production"])
              UI에서 클릭 한 번으로 필터링 가능, metadata보다 빠르고 직관적

    Returns:
        LangGraph/LangChain의 ainvoke/invoke에 전달할 config dict

    Example:
        config = get_runnable_config(
            trace_name="mit_search",
            user_id="user-123",
            mode="voice",
            tags=["voice", "dev"]
        )
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

    # Langfuse 싱글톤 초기화 확인
    _client = get_client()

    # CustomizedCallbackHandler 사용 (기본 CallbackHandler 대신)
    # update_trace=True로 설정하여 trace name이 업데이트되도록 함
    callback_handler = CustomizedCallbackHandler(update_trace=True)

    # Langfuse 2.x: metadata를 통해 trace 정보 전달
    # CallbackHandler가 on_chain_start에서 이 metadata를 읽어 trace를 생성합니다
    langfuse_metadata = {
        **(metadata or {}),
        **({"langfuse_user_id": user_id} if user_id else {}),
        **({"langfuse_session_id": session_id} if session_id else {}),
        **({"langfuse_mode": mode} if mode else {}),
        **({"langfuse_tags": tags} if tags else {}),
    }

    return {
        "callbacks": [callback_handler],
        **({"run_name": trace_name} if trace_name else {}),  # LangChain의 run_name이 trace name으로 사용됨
        **({"metadata": langfuse_metadata} if langfuse_metadata else {}),
    }
