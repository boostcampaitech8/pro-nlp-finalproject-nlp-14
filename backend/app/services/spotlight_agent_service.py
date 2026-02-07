"""Spotlight Agent 서비스 (회의 컨텍스트 없이 동작)"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.infrastructure.graph.integration.langfuse import get_runnable_config
from app.infrastructure.graph.orchestration.spotlight import get_spotlight_orchestration_app
from app.infrastructure.graph.spotlight_checkpointer import get_spotlight_checkpointer
from app.infrastructure.graph.orchestration.spotlight.state import RESET_TOOL_RESULTS
from app.infrastructure.streaming.event_stream_manager import stream_llm_tokens_only
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class SpotlightAgentService:
    """Spotlight 전용 Agent 서비스 (회의 컨텍스트 없음)"""

    THREAD_ID_PREFIX = "spotlight:"

    def __init__(self):
        self._app: CompiledStateGraph | None = None

    async def _get_app(self) -> CompiledStateGraph:
        """컴파일된 Spotlight 오케스트레이션 lazy 로드 (checkpointer 포함)"""
        if self._app is None:
            spotlight_checkpointer = await get_spotlight_checkpointer()
            self._app = await get_spotlight_orchestration_app(
                with_checkpointer=True, checkpointer=spotlight_checkpointer
            )
        return self._app

    def _get_thread_id(self, session_id: str) -> str:
        """session_id를 thread_id로 변환 (충돌 방지 prefix 추가)"""
        return f"{self.THREAD_ID_PREFIX}{session_id}"

    async def _get_user_context(self, user_id: str) -> dict:
        """사용자의 팀 정보 및 현재 시간 컨텍스트 조회"""
        from uuid import UUID

        from app.core.database import async_session_maker
        from app.services.team_service import TeamService

        current_time = datetime.now(timezone.utc).isoformat()

        try:
            user_uuid = UUID(str(user_id))
            async with async_session_maker() as db:
                service = TeamService(db)
                result = await service.list_my_teams(user_id=user_uuid, limit=10)
                return {
                    "user_id": user_id,
                    "teams": [{"id": str(t.id), "name": t.name} for t in result.items],
                    "current_time": current_time,
                }
        except Exception as e:
            logger.warning(f"사용자 컨텍스트 조회 실패: {e}")
            return {"user_id": user_id, "teams": [], "current_time": current_time}

    async def process_streaming(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
        hitl_action: str | None = None,
        hitl_params: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """SSE 스트리밍 응답 생성

        Args:
            user_input: 사용자 메시지
            session_id: Spotlight 세션 ID
            user_id: 사용자 ID
            hitl_action: HITL 응답 ('confirm' | 'cancel' | None)
            hitl_params: HITL 확인 시 사용자가 입력한 파라미터

        Yields:
            dict: SSE 이벤트 ({'type': 'status'|'token'|'done'|'error'|'hitl_request', ...})
        """
        logger.info(
            "Spotlight Agent 처리 시작: session_id=%s, user_input=%s..., hitl_action=%s",
            session_id,
            user_input[:50] if user_input else "",
            hitl_action,
        )

        # thread_id에 prefix 추가하여 충돌 방지
        thread_id = self._get_thread_id(session_id)

        # 상태 조회용 config (checkpointer)
        state_config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # 실행용 config (checkpointer + Langfuse)
        langfuse_config = get_runnable_config(
            trace_name="Spotlight",
            user_id=user_id,
            session_id=session_id,
            mode="spotlight",
            tags=["spotlight"],
            metadata={"workflow_version": "2.0", "session_id": session_id},
        )
        config = {
            **langfuse_config,
            **state_config,
        }

        app = await self._get_app()

        # HITL 응답: Command(resume)로 그래프 재개
        if hitl_action in ("confirm", "cancel"):
            resume_value = {"action": hitl_action}
            if hitl_params:
                resume_value["params"] = hitl_params
            graph_input = Command(resume=resume_value)
            logger.info(f"HITL 응답: action={hitl_action}, params={hitl_params}")
        else:
            # 일반 메시지: 이전 상태에서 컨텍스트 가져오기
            planning_context = ""
            user_context = None

            try:
                prev_state = await app.aget_state(state_config)
                if prev_state and prev_state.values:
                    prev_tool_results = prev_state.values.get("tool_results", "")
                    if prev_tool_results:
                        planning_context = f"[이전 도구 실행 결과]\n{prev_tool_results}"
                        logger.info(f"이전 도구 결과를 컨텍스트에 포함: {len(prev_tool_results)}자")

                    user_context = prev_state.values.get("user_context")

                    # 대기 중인 interrupt가 있으면 자동 취소
                    # NOTE: ainvoke로 cancel resume 시 tools→evaluator→generator 전체 실행됨.
                    # 추후 최적화 필요 시 aupdate_state로 직접 상태 업데이트 방식 검토.
                    if prev_state.tasks:
                        for task in prev_state.tasks:
                            if hasattr(task, 'interrupts') and task.interrupts:
                                logger.info(
                                    "HITL pending 자동 취소: session_id=%s, thread_id=%s",
                                    session_id, thread_id,
                                )
                                await app.ainvoke(
                                    Command(resume={"action": "cancel", "silent": True}),
                                    config,
                                )
                                break
            except Exception as e:
                logger.warning(f"이전 상태 조회 실패 (첫 턴일 수 있음): {e}")

            if user_context is None:
                user_context = await self._get_user_context(user_id)
                logger.info(f"사용자 컨텍스트 조회 완료: teams={len(user_context.get('teams', []))}개")

            graph_input = {
                "messages": [HumanMessage(content=user_input)] if user_input else [],
                "run_id": str(uuid.uuid4()),
                "user_id": user_id,
                "executed_at": datetime.now(timezone.utc),
                "retry_count": 0,
                "planning_context": planning_context,
                "user_context": user_context,
                "selected_tool": None,
                "tool_args": {},
                "tool_category": None,
                "plan": "",
                "need_tools": False,
                "can_answer": False,
                "missing_requirements": [],
                "next_subquery": None,
                "tool_results": RESET_TOOL_RESULTS,
            }

        try:
            async for event in stream_llm_tokens_only(app, graph_input, config):
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
        """세션의 대화 히스토리 조회 (HITL 상태 포함)

        Args:
            session_id: Spotlight 세션 ID

        Returns:
            list[dict]: 메시지 목록 (HITL pending 상태 포함)
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
                    history.append({
                        "role": "user",
                        "content": msg.content,
                        "type": "text",
                    })
                elif isinstance(msg, AIMessage):
                    history.append({
                        "role": "assistant",
                        "content": msg.content,
                        "type": "text",
                    })

            # pending interrupt 확인 (HITL 대기 중인 경우)
            if state.tasks:
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        hitl_data = task.interrupts[0].value
                        history.append({
                            "role": "assistant",
                            "content": hitl_data.get("confirmation_message", "작업을 수행할까요?"),
                            "type": "hitl",
                            "hitl_status": "pending",
                            "hitl_data": {
                                "tool_name": hitl_data.get("tool_name"),
                                "params": hitl_data.get("params", {}),
                                "params_display": hitl_data.get("params_display", {}),
                                "message": hitl_data.get("confirmation_message", ""),
                                "required_fields": hitl_data.get("required_fields", []),
                                "display_template": hitl_data.get("display_template"),
                                "hitl_request_id": hitl_data.get("hitl_request_id"),
                            },
                        })
                        logger.info(f"HITL pending interrupt 포함: {hitl_data.get('tool_name')}")
                        break

            # 🔧 Draft (스트리밍 중간 응답) 복원
            user_id = state.values.get("user_id")
            if user_id:
                redis = await get_redis()
                draft_key = f"spotlight:draft:{user_id}:{session_id}"
                draft_raw = await redis.get(draft_key)
                if draft_raw:
                    try:
                        draft_payload = json.loads(draft_raw)
                        draft_content = draft_payload.get("content", "")
                        if draft_content:
                            history.append({
                                "role": "assistant",
                                "content": draft_content,
                                "type": "draft",
                                "draft_data": {
                                    "request_id": draft_payload.get("request_id", ""),
                                    "updated_at": draft_payload.get("updated_at"),
                                },
                            })
                            logger.info(f"Draft 메시지 복원: session={session_id}")
                    except Exception as e:
                        logger.warning(f"Draft 메시지 복원 실패: {e}")

            return history

        except Exception as e:
            logger.error("히스토리 조회 오류: %s", e, exc_info=True)
            return []
