"""Langfuse LLM Observability 통합."""

from typing import Optional

from langfuse.langchain import CallbackHandler

from app.core.config import get_settings


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

    if not settings.langfuse_enabled:
        return {}

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return {}

    langfuse_metadata = {
        **({"langfuse_user_id": user_id} if user_id else {}),
        **({"langfuse_session_id": session_id} if session_id else {}),
        **(metadata or {}),
    }

    return {
        "callbacks": [CallbackHandler()],
        **({"run_name": trace_name} if trace_name else {}),
        **({"metadata": langfuse_metadata} if langfuse_metadata else {}),
    }
