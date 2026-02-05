"""Spotlight Agent 서비스 (회의 컨텍스트 없이 동작)"""

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.graph.integration.langfuse import get_runnable_config
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
            trace_name=f"spotlight:{session_id}",
            user_id=user_id,
            session_id=session_id,
            metadata={
                "interaction_mode": "spotlight",
                **({"hitl_action": hitl_action} if hitl_action else {}),
            },
        )
        config = {
            **langfuse_config,
            **state_config,
        }

        # HITL 상태 결정
        hitl_status = "none"
        if hitl_action == "confirm":
            hitl_status = "confirmed"
        elif hitl_action == "cancel":
            hitl_status = "cancelled"

        # 이전 상태에서 컨텍스트 및 HITL 관련 필드 가져오기
        planning_context = ""
        prev_selected_tool = None
        prev_tool_args = {}
        prev_tool_category = None
        prev_plan = ""
        prev_retry_count = 0
        user_context = None

        app = await self._get_app()
        try:
            prev_state = await app.aget_state(state_config)
            if prev_state and prev_state.values:
                # 이전 턴의 도구 결과를 컨텍스트에 포함
                prev_tool_results = prev_state.values.get("tool_results", "")
                if prev_tool_results:
                    planning_context = f"[이전 도구 실행 결과]\n{prev_tool_results}"
                    logger.info(f"이전 도구 결과를 컨텍스트에 포함: {len(prev_tool_results)}자")

                # 이전 상태에서 user_context 가져오기
                user_context = prev_state.values.get("user_context")

                # 🔧 HITL 응답 시 이전 상태의 도구 관련 필드 복원
                if hitl_action in ("confirm", "cancel"):
                    prev_selected_tool = prev_state.values.get("selected_tool")
                    prev_tool_args = prev_state.values.get("tool_args", {})
                    prev_tool_category = prev_state.values.get("tool_category")
                    prev_plan = prev_state.values.get("plan", "")
                    prev_retry_count = prev_state.values.get("retry_count", 0)
                    logger.info(
                        f"HITL 응답 - 이전 상태 복원: tool={prev_selected_tool}, "
                        f"args={prev_tool_args}, category={prev_tool_category}"
                    )
        except Exception as e:
            logger.warning(f"이전 상태 조회 실패 (첫 턴일 수 있음): {e}")

        # user_context가 없으면 조회
        if user_context is None:
            user_context = await self._get_user_context(user_id)
            logger.info(f"사용자 컨텍스트 조회 완료: teams={len(user_context.get('teams', []))}개")

        # 기본 상태 구성
        initial_state = {
            "messages": [HumanMessage(content=user_input)] if user_input else [],
            "run_id": str(uuid.uuid4()),
            "user_id": user_id,
            "executed_at": datetime.now(timezone.utc),
            "retry_count": prev_retry_count,
            "planning_context": planning_context,
            "interaction_mode": "spotlight",
            "hitl_status": hitl_status,
            "user_context": user_context,
        }

        # 🔧 새 메시지 전송 시 (HITL 응답이 아닌 경우) 이전 HITL 상태 초기화
        if hitl_action is None:
            initial_state.update({
                "hitl_tool_name": None,
                "hitl_extracted_params": None,
                "hitl_params_display": None,
                "hitl_missing_params": None,
                "hitl_confirmation_message": None,
                "hitl_required_fields": None,
                "hitl_display_template": None,
            })

        # 🔧 HITL 응답 시 이전 도구 상태 복원 (planner 건너뛰기)
        if hitl_action in ("confirm", "cancel") and prev_selected_tool:
            # 사용자가 입력한 파라미터를 이전 파라미터와 병합
            merged_tool_args = {**prev_tool_args}
            if hitl_params:
                merged_tool_args.update(hitl_params)
                logger.info(f"HITL 사용자 입력 파라미터 병합: {hitl_params}")

            initial_state.update({
                "selected_tool": prev_selected_tool,
                "tool_args": merged_tool_args,
                "tool_category": prev_tool_category,
                "plan": prev_plan,
                "skip_planning": True,  # planner 건너뛰고 바로 tools 노드로
            })
            logger.info(f"HITL 응답: skip_planning=True, selected_tool={prev_selected_tool}, args={merged_tool_args}")

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

            # 🔧 HITL pending 상태 확인 및 추가 (유효한 HITL 요청인 경우에만)
            hitl_status = state.values.get("hitl_status")
            hitl_tool_name = state.values.get("hitl_tool_name")

            # pending 상태이면서 tool_name이 실제로 존재하는 경우에만 HITL 메시지 추가
            if hitl_status == "pending" and hitl_tool_name:
                hitl_params = state.values.get("hitl_extracted_params", {})
                hitl_message = state.values.get("hitl_confirmation_message", "")
                hitl_required_fields = state.values.get("hitl_required_fields", [])

                history.append({
                    "role": "assistant",
                    "content": hitl_message or "작업을 수행할까요?",
                    "type": "hitl",
                    "hitl_status": "pending",
                    "hitl_data": {
                        "tool_name": hitl_tool_name,
                        "params": hitl_params,
                        "params_display": state.values.get("hitl_params_display", {}),
                        "message": hitl_message,
                        "required_fields": hitl_required_fields,
                        "display_template": state.values.get("hitl_display_template"),
                    },
                })
                logger.info(f"HITL pending 상태 포함: {hitl_tool_name}")

            return history

        except Exception as e:
            logger.error("히스토리 조회 오류: %s", e, exc_info=True)
            return []
