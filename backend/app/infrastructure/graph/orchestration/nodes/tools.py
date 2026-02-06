"""Unified Tool Execution Node with HITL Support

This node handles execution of both Query and Mutation tools.
For Mutation tools in Spotlight mode, it uses LangGraph interrupt() for HITL.
"""

import logging
from uuid import UUID, uuid4

from langgraph.types import interrupt

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_maker
from app.models.team import TeamMember

from ..state import OrchestrationState
from ..tools.base import ToolCategory
from ..tools.registry import get_tool_by_name, get_tool_metadata

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


async def execute_tools(state: OrchestrationState) -> OrchestrationState:
    """통합 도구 실행 노드 (HITL 지원 - interrupt 방식)

    Contract:
        reads: selected_tool, tool_args, tool_category, user_id
        writes: tool_results
        side-effects: Tool 실행 (DB/Neo4j 작업), Mutation 시 interrupt()로 HITL 중단
        failures: TOOL_NOT_FOUND, TOOL_EXECUTION_ERROR

    Returns:
        OrchestrationState: State update with tool results
    """
    logger.info("Tool execution node entered")

    selected_tool = state.get("selected_tool")
    interaction_mode = "voice" if state.get("meeting_id") else "spotlight"
    user_id = state.get("user_id")
    tool_args = state.get("tool_args", {})

    # No tool selected - return early
    if not selected_tool:
        logger.warning("No tool selected")
        return OrchestrationState(
            tool_results="도구가 선택되지 않았습니다.",
            selected_tool=None,
            tool_args={},
            tool_category=None,
            auto_cancelled=False,
        )

    # Get the tool (StructuredTool)
    tool = get_tool_by_name(selected_tool)
    if not tool:
        logger.error(f"Tool not found: {selected_tool}")
        return OrchestrationState(
            tool_results=f"'{selected_tool}' 도구를 찾을 수 없습니다.",
            selected_tool=None,
            tool_args={},
            tool_category=None,
            auto_cancelled=False,
        )

    # Get tool metadata
    metadata = get_tool_metadata(selected_tool)
    tool_category_from_meta = metadata.get("category", "query") if metadata else "query"

    logger.info(
        f"Executing tool: {selected_tool}, category: {tool_category_from_meta}, "
        f"mode: {interaction_mode}"
    )

    # === HITL Flow for Mutation Tools (interrupt 방식) ===
    if tool_category_from_meta == ToolCategory.MUTATION.value:
        # Voice 모드에서는 mutation 도구 사용 불가
        if interaction_mode == "voice":
            logger.warning(f"Mutation tool {selected_tool} not allowed in Voice mode")
            return OrchestrationState(
                tool_results=f"'{tool.description}' 작업은 Spotlight 모드에서만 가능합니다.",
                auto_cancelled=False,
            )

        # HITL 데이터 구성
        logger.info(f"[HITL] Mutation 도구 감지, interrupt 준비: {selected_tool}")
        confirmation_message = generate_confirmation_message(
            selected_tool, tool_args, metadata, tool.description
        )
        hitl_request_id = str(uuid4())

        # required_fields 빌드 (프론트엔드 입력 폼용)
        required_fields = []
        options_cache: dict[str, list[dict]] = {}
        hitl_fields = metadata.get("hitl_fields", {}) if metadata else {}

        for field_name, field_config in hitl_fields.items():
            options_source = field_config.get("options_source")

            if options_source:
                if options_source not in options_cache:
                    options_cache[options_source] = await load_dynamic_options(
                        options_source, user_id
                    )

            default_value = tool_args.get(field_name)

            # select 타입: UUID → display label 변환
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
                "default_value": default_value,
                "default_display": default_display,
            }

            if options_source and options_source in options_cache:
                field_data["options"] = options_cache[options_source]
                if field_data["options"] and field_data["input_type"] == "text":
                    field_data["input_type"] = "select"

            required_fields.append(field_data)

        # params_display 빌드 (UUID → 이름 변환)
        params_display = {}
        for field_name, field_config in hitl_fields.items():
            if field_name in tool_args and tool_args.get(field_name) is not None:
                value = tool_args[field_name]
                display_value = str(value)

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

        # interrupt()! 그래프 자동 중단 → checkpointer에 상태 저장 → 재개 대기
        user_response = interrupt(hitl_data) or {}

        # 재개됨: 사용자 응답 처리
        if user_response.get("action") == "cancel":
            logger.info(f"[HITL] 사용자 취소: {selected_tool}")
            is_silent = bool(user_response.get("silent"))
            return OrchestrationState(
                tool_results="" if is_silent else "작업이 취소되었습니다.",
                selected_tool=None,
                tool_args={},
                tool_category=None,
                auto_cancelled=is_silent,
            )

        # confirm: 사용자 수정 파라미터 병합
        logger.info(f"[HITL] 사용자 확인: {selected_tool}")
        if user_response.get("params"):
            tool_args = {**tool_args, **user_response["params"]}
            logger.info(f"[HITL] 사용자 파라미터 병합: {user_response['params']}")

    # === Execute the Tool ===
    try:
        logger.info(f"Executing tool {selected_tool} with args: {tool_args}")

        invoke_args = {"_user_id": user_id, **tool_args}
        result = await tool.coroutine(**invoke_args)

        logger.info(f"Tool execution result: {result}")

        # Format result for state
        if isinstance(result, dict):
            if result.get("error"):
                tool_results = f"오류: {result['error']}"
            elif result.get("message"):
                tool_results = result["message"]
            else:
                tool_results = str(result)
        else:
            tool_results = str(result)

        return OrchestrationState(
            tool_results=tool_results,
            selected_tool=None,
            tool_args={},
            tool_category=None,
            auto_cancelled=False,
        )

    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return OrchestrationState(
            tool_results=f"도구 실행 중 오류가 발생했습니다: {str(e)}",
            selected_tool=None,
            tool_args={},
            tool_category=None,
            auto_cancelled=False,
        )
