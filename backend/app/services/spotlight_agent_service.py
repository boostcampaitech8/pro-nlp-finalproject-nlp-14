"""Spotlight Agent 서비스 (회의 컨텍스트 없이 동작)"""

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.orchestration import get_compiled_app
from app.infrastructure.streaming.event_stream_manager import stream_llm_tokens_only

logger = logging.getLogger(__name__)


class SpotlightAgentService:
    """Spotlight 전용 Agent 서비스 (회의 컨텍스트 없음)"""

    THREAD_ID_PREFIX = "spotlight:"

    def __init__(self):
        self._app: CompiledStateGraph | None = None

    async def _get_app(self) -> CompiledStateGraph:
        """컴파일된 앱 lazy 로드 (checkpointer 포함)"""
        if self._app is None:
            self._app = await get_compiled_app(with_checkpointer=True)
        return self._app

    def _get_thread_id(self, session_id: str) -> str:
        """session_id를 thread_id로 변환 (충돌 방지 prefix 추가)"""
        return f"{self.THREAD_ID_PREFIX}{session_id}"

    async def process_streaming(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
    ) -> AsyncGenerator[dict, None]:
        """SSE 스트리밍 응답 생성

        Args:
            user_input: 사용자 메시지
            session_id: Spotlight 세션 ID
            user_id: 사용자 ID

        Yields:
            dict: SSE 이벤트 ({'type': 'status'|'token'|'done'|'error', ...})
        """
        logger.info(
            "Spotlight Agent 처리 시작: session_id=%s, user_input=%s...",
            session_id,
            user_input[:50] if user_input else "",
        )

        # thread_id에 prefix 추가하여 충돌 방지
        thread_id = self._get_thread_id(session_id)

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "run_id": str(uuid.uuid4()),
            "user_id": user_id,
            "executed_at": datetime.now(timezone.utc),
            "retry_count": 0,
            "planning_context": "",  # 빈 문자열 -> Planning 노드에서 "없음" 처리
        }

        try:
            app = await self._get_app()
            async for event in stream_llm_tokens_only(app, initial_state, config):
                yield event

            logger.info("Spotlight Agent 처리 완료 (thread_id=%s)", thread_id)

        except Exception as e:
            logger.error("Spotlight Agent 오류: %s", e, exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def get_history(self, session_id: str) -> list[dict]:
        """세션의 대화 히스토리 조회

        Args:
            session_id: Spotlight 세션 ID

        Returns:
            list[dict]: 메시지 목록 [{'role': 'user'|'assistant', 'content': str}]
        """
        thread_id = self._get_thread_id(session_id)
        config = {"configurable": {"thread_id": thread_id}}

        try:
            app = await self._get_app()
            state = await app.aget_state(config)

            if not state or not state.values:
                return []

            messages = state.values.get("messages", [])
            history = []

            for msg in messages:
                if isinstance(msg, HumanMessage):
                    history.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    history.append({"role": "assistant", "content": msg.content})

            return history

        except Exception as e:
            logger.error("히스토리 조회 오류: %s", e, exc_info=True)
            return []
