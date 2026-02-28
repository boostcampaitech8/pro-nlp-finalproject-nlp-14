"""Unified Tool Execution Node with HITL Support (interrupt 기반)"""

import json
import logging
from uuid import UUID, uuid4

from langgraph.types import interrupt
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from langchain_core.messages import ToolMessage

from app.core.database import async_session_maker
from app.models.team import TeamMember

from ..state import SpotlightOrchestrationState
from app.infrastructure.graph.orchestration.shared.state_utils import RESET_TOOL_RESULTS
from app.infrastructure.graph.orchestration.shared.tools.base import ToolCategory
from app.infrastructure.graph.orchestration.shared.tools.registry import get_tool_by_name, get_tool_metadata

logger = logging.getLogger(__name__)


async def load_dynamic_options(options_source: str, user_id: str) -> list[dict]:
    """동적 옵션 로딩 (예: 사용자의 팀 목록)

    Args:
        options_source: 옵션 소스 식별자 (예: 'user_teams')
        user_id: 현재 사용자 ID

    Returns:
        list[dict]: [{"value": "uuid", "label": "이름"}, ...]
    """
    if options_source == "user_teams":
        try:
            user_uuid = UUID(str(user_id))
            async with async_session_maker() as db:
                result = await db.execute(
                    select(TeamMember)
                    .options(selectinload(TeamMember.team))
                    .where(TeamMember.user_id == user_uuid)
                )
                members = result.scalars().all()
                return [
                    {"value": str(m.team_id), "label": m.team.name if m.team else str(m.team_id)}
                    for m in members
                ]
        except Exception as e:
            logger.error(f"Failed to load user teams: {e}")
            return []

    # 다른 옵션 소스 추가 가능
    logger.warning(f"Unknown options_source: {options_source}")
    return []


def generate_confirmation_message(
    tool_name: str, tool_args: dict, metadata: dict | None, tool_description: str
) -> str:
    """메타데이터 기반 확인 메시지 생성

    Args:
        tool_name: 도구 이름
        tool_args: 도구 인자
        metadata: 도구 메타데이터
        tool_description: 도구 설명

    Returns:
        str: 확인 메시지
    """
    if not metadata:
        return f"{tool_name} 작업을 수행할까요?"

    # display_template이 있으면 사용
    template = metadata.get("display_template")
    if template:
        # {{param_name}} 형식의 플레이스홀더를 값으로 대체
        for key, value in tool_args.items():
            template = template.replace(f"{{{{{key}}}}}", str(value or ""))
        return template

    # 기본 메시지
    lines = [f"{tool_description}을(를) 수행할까요?"]

    # 추출된 파라미터가 있으면 표시
    extracted_items = [
        (key, value) for key, value in tool_args.items() if value is not None
    ]

    if extracted_items:
        lines.append("")
        lines.append("입력된 정보:")
        for key, value in extracted_items:
            lines.append(f"  - {key}: {value}")

    return "\n".join(lines)


def get_tool_category_from_metadata(tool_name: str) -> str:
    """메타데이터에서 도구 카테고리 가져오기

    Args:
        tool_name: 도구 이름

    Returns:
        str: 카테고리 ('query' 또는 'mutation')
    """
    metadata = get_tool_metadata(tool_name)
    if metadata:
        return metadata.get("category", "query")
    return "query"


def _get_tool_call_id(state: SpotlightOrchestrationState) -> str:
    """planner의 AIMessage에서 tool_call_id 추출."""
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return messages[-1].tool_calls[0]["id"]
    return "unknown"


async def execute_tools(state: SpotlightOrchestrationState) -> SpotlightOrchestrationState:
    """Spotlight 도구 실행 노드 (HITL interrupt 기반)

    Spotlight 모드는 Query + Mutation 도구를 모두 지원하며,
    Mutation 도구 실행 전에는 interrupt()로 사용자 확인(HITL) 절차를 거칩니다.

    Contract:
        reads: selected_tool, tool_args, user_id
        writes: tool_results
        side-effects: Tool 실행 (DB/Neo4j 작업), Mutation 시 interrupt()로 중단
        failures: TOOL_NOT_FOUND, TOOL_EXECUTION_ERROR
    """
    logger.info("Spotlight Tool execution node entered")

    selected_tool = state.get("selected_tool")
    user_id = state.get("user_id")
    tool_args = state.get("tool_args", {})

    tool_call_id = _get_tool_call_id(state)

    # No tool selected - return early
    if not selected_tool:
        logger.warning("No tool selected")
        content = "도구가 선택되지 않았습니다."
        return SpotlightOrchestrationState(
            messages=[ToolMessage(content=content, tool_call_id=tool_call_id, name="unknown")],
            tool_results=content,
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    # Get the tool (StructuredTool)
    tool = get_tool_by_name(selected_tool)
    if not tool:
        logger.error(f"Tool not found: {selected_tool}")
        content = f"'{selected_tool}' 도구를 찾을 수 없습니다."
        return SpotlightOrchestrationState(
            messages=[ToolMessage(content=content, tool_call_id=tool_call_id, name=selected_tool)],
            tool_results=content,
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    # Get tool metadata
    metadata = get_tool_metadata(selected_tool)
    tool_category_from_meta = metadata.get("category", "query") if metadata else "query"

    logger.info(
        f"Executing tool: {selected_tool}, category: {tool_category_from_meta}"
    )

    # === HITL Flow for Mutation Tools ===
    if tool_category_from_meta == ToolCategory.MUTATION.value:
        logger.info(f"[HITL] Mutation 도구 감지, interrupt 준비: {selected_tool}")

        # Generate confirmation message
        confirmation_message = generate_confirmation_message(
            selected_tool, tool_args, metadata, tool.description
        )
        hitl_request_id = str(uuid4())

        # Generate required fields schema for frontend input form
        required_fields = []
        options_cache: dict[str, list[dict]] = {}

        # hitl_fields에서 필드 정보 가져오기
        hitl_fields = metadata.get("hitl_fields", {}) if metadata else {}

        for field_name, field_config in hitl_fields.items():
            options_source = field_config.get("options_source")

            # 동적 옵션 로딩
            if options_source:
                if options_source not in options_cache:
                    options_cache[options_source] = await load_dynamic_options(
                        options_source, user_id
                    )

            # LLM이 추출한 값을 default_value로 설정 (모든 필드 포함)
            default_value = tool_args.get(field_name)

            # select 타입이고 옵션이 있으면, UUID를 display 값으로 변환
            default_display = None
            if options_source and options_source in options_cache and default_value:
                for opt in options_cache[options_source]:
                    if opt["value"] == str(default_value):
                        default_display = opt["label"]
                        break

            field_data = {
                "name": field_name,
                "description": field_config.get("placeholder", field_name),
                "type": "str",
                "required": field_config.get("required", True),
                "input_type": field_config.get("input_type", "text"),
                "placeholder": field_config.get("placeholder", ""),
                "options": [],
                "default_value": default_value,  # LLM 추출 값 (없으면 None)
                "default_display": default_display,  # UUID → 이름 변환 (select용)
            }

            # 동적 옵션 적용
            if options_source and options_source in options_cache:
                field_data["options"] = options_cache[options_source]
                # 옵션이 있으면 input_type을 select로 설정
                if field_data["options"] and field_data["input_type"] == "text":
                    field_data["input_type"] = "select"

            required_fields.append(field_data)

        # 이미 추출된 파라미터의 표시용 값 생성 (UUID → 이름)
        params_display = {}
        for field_name, field_config in hitl_fields.items():
            if field_name in tool_args and tool_args.get(field_name) is not None:
                value = tool_args[field_name]
                display_value = str(value)

                # 동적 옵션이 있으면 라벨로 변환
                options_source = field_config.get("options_source")
                if options_source and options_source in options_cache:
                    for opt in options_cache[options_source]:
                        if opt["value"] == str(value):
                            display_value = opt["label"]
                            break

                params_display[field_name] = display_value

        display_template = metadata.get("display_template") if metadata else None

        hitl_data = {
            "tool_name": selected_tool,
            "params": tool_args,
            "params_display": params_display,
            "required_fields": required_fields,
            "display_template": display_template,
            "confirmation_message": confirmation_message,
            "hitl_request_id": hitl_request_id,
        }

        user_response = interrupt(hitl_data)

        # 사용자 취소
        if user_response.get("action") == "cancel":
            silent = user_response.get("silent", False)
            logger.info(f"[HITL] 사용자 취소: {selected_tool}, silent={silent}")
            if silent:
                # Silent cancel: RESET_TOOL_RESULTS로 누적된 tool_results 초기화
                # → route_after_tools에서 빈 문자열로 판별 → END
                return SpotlightOrchestrationState(
                    messages=[ToolMessage(content="", tool_call_id=tool_call_id, name=selected_tool)],
                    tool_results=RESET_TOOL_RESULTS,
                    tool_execution_status="cancelled",
                    selected_tool=None,
                    tool_args={},
                    tool_category=None,
                )
            # 명시적 cancel: 취소 메시지를 tool_results에 기록
            content = "작업이 취소되었습니다."
            return SpotlightOrchestrationState(
                messages=[ToolMessage(content=content, tool_call_id=tool_call_id, name=selected_tool)],
                tool_results=content,
                tool_execution_status="cancelled",
                selected_tool=None,
                tool_args={},
                tool_category=None,
            )

        # 사용자 확인 (파라미터 병합)
        if user_response.get("params"):
            tool_args = {**tool_args, **user_response["params"]}
            logger.info(f"[HITL] 사용자 파라미터 병합: {user_response['params']}")

    # === Execute the Tool ===
    try:
        logger.info(f"Executing tool {selected_tool} with args: {tool_args}")

        # tool.coroutine 직접 호출 (_user_id는 스키마에 없어서 ainvoke로는 전달 불가)
        invoke_args = {"_user_id": user_id, **tool_args}
        result = await tool.coroutine(**invoke_args)

        logger.info(f"Tool execution result: {result}")

        # Format result for state
        if isinstance(result, dict) and result.get("error"):
            tool_results = f"\n[{selected_tool} 오류]\n{result['error']}\n"
        elif isinstance(result, dict) and result.get("message"):
            tool_results = f"\n[{selected_tool} 결과]\n{result['message']}\n"
        else:
            result_str = json.dumps(result, ensure_ascii=False, default=str) if isinstance(result, dict) else str(result)
            tool_results = f"\n[{selected_tool} 결과]\n{result_str}\n"

        return SpotlightOrchestrationState(
            messages=[ToolMessage(content=tool_results, tool_call_id=tool_call_id, name=selected_tool)],
            tool_results=tool_results,
            tool_execution_status="executed",
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )

    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        content = f"\n[{selected_tool} 오류]\n{str(e)}\n"
        return SpotlightOrchestrationState(
            messages=[ToolMessage(content=content, tool_call_id=tool_call_id, name=selected_tool or "unknown")],
            tool_results=content,
            tool_execution_status="error",
            selected_tool=None,
            tool_args={},
            tool_category=None,
        )
