"""Agent 서비스 (LLM 스트리밍 + Orchestration Graph + Checkpointer)

멀티턴 대화 지원:
- thread_id = meeting_id로 대화 컨텍스트 유지
- AsyncPostgresSaver로 상태 영속화
- 워커 재시작 시 자동 복구
"""

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.agent import ClovaStudioLLMClient
from app.infrastructure.context import ContextBuilder, ContextManager
from app.infrastructure.graph.integration.langfuse import get_runnable_config
from app.infrastructure.graph.orchestration.voice import get_voice_orchestration_app
from app.infrastructure.streaming.event_stream_manager import stream_llm_tokens_only

logger = logging.getLogger(__name__)


class AgentService:
    """LLM 스트리밍 및 Orchestration 기반 응답 서비스

    멀티턴 지원:
    - thread_id = meeting_id로 대화 컨텍스트 유지
    - AsyncPostgresSaver로 상태 영속화
    - 워커 재시작 시 자동 복구
    """

    def __init__(self, llm_client: ClovaStudioLLMClient):
        self.llm_client = llm_client
        self._app: CompiledStateGraph | None = None  # lazy init

    async def _get_app(self) -> CompiledStateGraph:
        """컴파일된 Voice 오케스트레이션 lazy 로드 (checkpointer 포함)"""
        if self._app is None:
            self._app = await get_voice_orchestration_app(with_checkpointer=True)
        return self._app

    async def process_streaming(
        self,
        user_input: str,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """기본 LLM 스트리밍 (기존 방식)"""
        logger.info("Agent 처리 시작: user_input=%s...", user_input[:100])

        async for token in self.llm_client.stream(user_input, system_prompt):
            yield token

        logger.info("Agent 처리 완료")

    async def process_with_context(
        self,
        user_input: str,
        meeting_id: str,
        user_id: str,
        ctx_manager: ContextManager,
    ) -> str:
        """Context Engineering + Orchestration Graph + Checkpointer 기반 처리

        Args:
            user_input: 사용자 질의
            meeting_id: 회의 ID (thread_id로 사용하여 멀티턴 유지)
            user_id: 사용자 ID
            ctx_manager: 이미 업데이트된 ContextManager

        Returns:
            str: 에이전트 응답
        """
        logger.info(
            "Agent Context 처리 시작: meeting_id=%s, user_input=%s...",
            meeting_id,
            user_input[:50] if user_input else "",
        )

        # 대기 중/실행 중인 L1 처리 완료 대기
        l1_was_busy = ctx_manager.has_pending_l1 or ctx_manager.is_l1_running
        await ctx_manager.await_l1_idle()
        if l1_was_busy:
            logger.info("L1 처리 완료: %d개 세그먼트", len(ctx_manager.l1_segments))

        # ContextBuilder로 컨텍스트 구성
        builder = ContextBuilder()
        planning_context = builder.build_planning_input_context(
            ctx_manager, user_query=user_input
        )

        # Semantic Search 기반 추가 컨텍스트 구성 (비동기 배치 임베딩)
        additional_context = await builder.build_additional_context_with_search_async(
            ctx_manager,
            user_input,
            top_k=ctx_manager.config.topic_search_top_k,
            threshold=ctx_manager.config.topic_search_threshold,
        )

        # Orchestration Graph 초기 상태 구성
        # 주의: messages에 현재 질문만 넣음 → checkpointer가 이전 대화를 복원하여 병합
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "run_id": str(uuid.uuid4()),
            "user_id": user_id,
            "meeting_id": meeting_id,  # Voice 전용
            "executed_at": datetime.now(timezone.utc),
            "retry_count": 0,
            "planning_context": planning_context,
            "additional_context": additional_context,
        }

        # thread_id 기반 config (멀티턴 핵심) + Langfuse 트레이싱
        langfuse_config = get_runnable_config(
            trace_name="Voice",
            user_id=user_id,
            mode="voice",
            tags=["voice"],
            metadata={"workflow_version": "2.0", "meeting_id": meeting_id},
        )
        config = {
            **langfuse_config,
            "configurable": {
                "thread_id": meeting_id,  # 회의별 대화 컨텍스트 유지
            },
        }

        try:
            # checkpointer 포함된 앱으로 실행 (thread_id config 전달)
            # 그래프가 전체 플로우 실행: planner → mit_tools → evaluator → generator
            # checkpointer가 이전 messages를 복원하여 멀티턴 대화 유지
            app = await self._get_app()
            final_state = await app.ainvoke(initial_state, config)
            response = final_state.get("response", "")

            # Langfuse trace에 실제 user input/output 기록
            try:
                from langfuse import get_client
                client = get_client()
                client.update_current_trace(
                    input={"user_message": user_input},
                    output={"assistant_response": response}
                )
            except Exception as e:
                logger.warning(f"Langfuse trace 업데이트 실패: {e}")

            logger.info("Agent Context 처리 완료 (thread_id=%s)", meeting_id)
            return response

        except Exception as e:
            logger.error("Orchestration 실행 실패: %s", e, exc_info=True)
            raise

    async def process_with_context_streaming(
        self,
        user_input: str,
        meeting_id: str,
        user_id: str,
        ctx_manager: ContextManager,
    ) -> AsyncGenerator[dict, None]:
        """Context Engineering + Orchestration + Event Streaming

        DB 세션 없이 스트리밍만 수행합니다.
        Context 로드는 호출 전에 미리 완료되어야 합니다.

        Args:
            user_input: 사용자 질의
            meeting_id: 회의 ID (thread_id로 사용하여 멀티턴 유지)
            user_id: 사용자 ID
            ctx_manager: 이미 업데이트된 ContextManager

        Yields:
            dict: SSE 이벤트 ({'type': 'token', 'content': str} or {'type': 'done'})
        """
        logger.info(
            "Agent Context Streaming 시작: meeting_id=%s, user_input=%s...",
            meeting_id,
            user_input[:50] if user_input else "",
        )

        # 대기 중/실행 중인 L1 처리 완료 대기
        l1_was_busy = ctx_manager.has_pending_l1 or ctx_manager.is_l1_running
        await ctx_manager.await_l1_idle()
        if l1_was_busy:
            logger.info("L1 처리 완료: %d개 세그먼트", len(ctx_manager.l1_segments))

        # 3. ContextBuilder로 planning context 구성
        builder = ContextBuilder()
        planning_context = builder.build_planning_input_context(
            ctx_manager, user_query=user_input
        )

        # Semantic Search 기반 추가 컨텍스트 구성 (비동기 배치 임베딩)
        additional_context = await builder.build_additional_context_with_search_async(
            ctx_manager,
            user_input,
            top_k=ctx_manager.config.topic_search_top_k,
            threshold=ctx_manager.config.topic_search_threshold,
        )

        # 4. Orchestration Graph 초기 상태 구성
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "run_id": str(uuid.uuid4()),
            "user_id": user_id,
            "meeting_id": meeting_id,  # Voice 전용
            "executed_at": datetime.now(timezone.utc),
            "retry_count": 0,
            "planning_context": planning_context,
            "additional_context": additional_context,
        }

        # thread_id 기반 config (멀티턴 핵심) + Langfuse 트레이싱
        langfuse_config = get_runnable_config(
            trace_name="Voice",
            user_id=user_id,
            mode="voice",
            tags=["voice"],
            metadata={"workflow_version": "2.0", "meeting_id": meeting_id},
        )
        config = {
            **langfuse_config,
            "configurable": {
                "thread_id": meeting_id,
            },
        }

        try:
            # astream_events()로 실행 (Planning 포함)
            app = await self._get_app()
            async for event in stream_llm_tokens_only(app, initial_state, config):
                yield event

            logger.info("Agent Context Streaming 완료 (thread_id=%s)", meeting_id)

        except Exception as e:
            logger.error("Streaming 실행 실패: %s", e, exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
