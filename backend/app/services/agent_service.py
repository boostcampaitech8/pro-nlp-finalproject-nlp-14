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
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.agent import ClovaStudioLLMClient
from app.infrastructure.context import ContextBuilder, ContextManager
from app.infrastructure.graph.orchestration import get_compiled_app
from app.infrastructure.graph.orchestration.nodes.planning import create_plan

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
        """컴파일된 앱 lazy 로드 (checkpointer 포함)"""
        if self._app is None:
            self._app = await get_compiled_app(with_checkpointer=True)
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
        db: AsyncSession,
    ) -> str:
        """Context Engineering + Orchestration Graph + Checkpointer 기반 처리

        Args:
            user_input: 사용자 질의
            meeting_id: 회의 ID (thread_id로 사용하여 멀티턴 유지)
            user_id: 사용자 ID
            db: DB 세션

        Returns:
            str: 에이전트 응답
        """
        logger.info(
            "Agent Context 처리 시작: meeting_id=%s, user_input=%s...",
            meeting_id,
            user_input[:50] if user_input else "",
        )

        # 1. ContextManager 초기화 및 DB에서 발화 로드 (L0/L1)
        ctx_manager = ContextManager(meeting_id=meeting_id, db_session=db)
        loaded = await ctx_manager.load_from_db()
        logger.info("DB에서 %d개 발화 로드됨", loaded)

        # 2. 대기 중인 L1 처리 완료 대기
        if ctx_manager.has_pending_l1:
            await ctx_manager.await_pending_l1()
            logger.info("L1 처리 완료: %d개 세그먼트", len(ctx_manager.l1_segments))

        # 3. ContextBuilder로 planning context 구성 (질문 포함)
        builder = ContextBuilder()
        planning_context = builder.build_planning_input_context(
            ctx_manager, user_query=user_input
        )

        # 4. Orchestration Graph 초기 상태 구성
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "run_id": str(uuid.uuid4()),
            "user_id": user_id,
            "executed_at": datetime.now(timezone.utc),
            "retry_count": 0,
            "planning_context": planning_context,
        }

        # 5. thread_id 기반 config (멀티턴 핵심)
        config = {
            "configurable": {
                "thread_id": meeting_id,  # 회의별 대화 컨텍스트 유지
            }
        }

        try:
            # 6. Planning 실행 (1단계: 컨텍스트 기반 계획 수립)
            planning_result = await create_plan(initial_state)
            required_topics = planning_result.get("required_topics", [])

            logger.info("Planning 완료: required_topics=%s", required_topics)

            # 7. 추가 토픽 컨텍스트 구성 (2단계)
            additional_context, missing = builder.build_required_topic_context(
                ctx_manager, required_topics
            )
            if missing:
                logger.warning("토픽 매칭 실패: %s", missing)

            # 8. 최종 상태 구성 후 Orchestration 실행
            full_state = {
                **initial_state,
                **planning_result,
                "additional_context": additional_context,
                "skip_planning": True,  # 이미 planning 완료
            }

            # 9. checkpointer 포함된 앱으로 실행 (thread_id config 전달)
            app = await self._get_app()
            final_state = await app.ainvoke(full_state, config)
            response = final_state.get("response", "")

            logger.info("Agent Context 처리 완료 (thread_id=%s)", meeting_id)
            return response

        except Exception as e:
            logger.error("Orchestration 실행 실패: %s", e, exc_info=True)
            raise
