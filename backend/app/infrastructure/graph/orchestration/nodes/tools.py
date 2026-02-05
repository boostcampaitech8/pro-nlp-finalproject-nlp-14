"""Unified Tool Execution Node with HITL Support

This node handles execution of both Query and Mutation tools.
For Mutation tools in Spotlight mode, it initiates HITL flow.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_maker
from app.models.team import TeamMember

from ..state import OrchestrationState
from ..tools.base import ToolCategory
from ..tools.registry import InteractionMode, get_tool_by_name, get_tool_metadata

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
    """통합 도구 실행 노드 (HITL 지원)

    Contract:
        reads: selected_tool, tool_args, tool_category, hitl_status, interaction_mode, user_id
        writes: tool_results, hitl_status, hitl_tool_name, hitl_extracted_params,
                hitl_confirmation_message
        side-effects: Tool 실행 (DB/Neo4j 작업)
        failures: TOOL_NOT_FOUND, TOOL_EXECUTION_ERROR

    Returns:
        OrchestrationState: State update with tool results or HITL request
    """
    logger.info("Tool execution node entered")

    selected_tool = state.get("selected_tool")
    hitl_status = state.get("hitl_status", "none")
    interaction_mode = state.get("interaction_mode", "spotlight")
    user_id = state.get("user_id")
    tool_args = state.get("tool_args", {})

    # No tool selected - return early
    if not selected_tool:
        logger.warning("No tool selected")
        return OrchestrationState(tool_results="도구가 선택되지 않았습니다.")

    # Get the tool (StructuredTool)
    tool = get_tool_by_name(selected_tool)
    if not tool:
        logger.error(f"Tool not found: {selected_tool}")
        return OrchestrationState(tool_results=f"'{selected_tool}' 도구를 찾을 수 없습니다.")

    # Get tool metadata
    metadata = get_tool_metadata(selected_tool)
    tool_category_from_meta = metadata.get("category", "query") if metadata else "query"

    logger.info(
        f"Executing tool: {selected_tool}, category: {tool_category_from_meta}, "
        f"hitl_status: {hitl_status}, mode: {interaction_mode}"
    )

    # === HITL Flow for Mutation Tools ===
    if tool_category_from_meta == ToolCategory.MUTATION.value:
        # Check if Mutation tool is allowed in current mode
        if interaction_mode == InteractionMode.VOICE.value:
            logger.warning(f"Mutation tool {selected_tool} not allowed in Voice mode")
            return OrchestrationState(
                tool_results=f"'{tool.description}' 작업은 Spotlight 모드에서만 가능합니다."
            )

        # HITL not yet initiated - request confirmation
        if hitl_status == "none":
            logger.info(f"Initiating HITL for mutation tool: {selected_tool}")

            # Generate confirmation message
            confirmation_message = generate_confirmation_message(
                selected_tool, tool_args, metadata, tool.description
            )

            # Generate required fields schema for frontend input form
            # Only include fields NOT already extracted by LLM
            required_fields = []
            # 동적 옵션 캐시 (params_display 생성용)
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

            return OrchestrationState(
                hitl_status="pending",
                hitl_tool_name=selected_tool,
                hitl_extracted_params=tool_args,
                hitl_params_display=params_display,  # UUID → 이름 변환된 표시용 값
                hitl_confirmation_message=confirmation_message,
                hitl_required_fields=required_fields,
                hitl_display_template=display_template,  # 자연어 템플릿
                tool_results="",  # No results yet
            )

        # HITL cancelled by user
        if hitl_status == "cancelled":
            logger.info(f"HITL cancelled for tool: {selected_tool}")
            return OrchestrationState(
                hitl_status="none",
                hitl_tool_name=None,
                hitl_extracted_params=None,
                hitl_confirmation_message=None,
                tool_results="작업이 취소되었습니다.",
            )

        # HITL pending - should not reach here (graph routes to END)
        if hitl_status == "pending":
            logger.warning("Tool execution called with hitl_status=pending")
            return OrchestrationState(tool_results="사용자 확인을 기다리고 있습니다.")

        # HITL confirmed - proceed with execution
        if hitl_status == "confirmed":
            logger.info(f"HITL confirmed, executing mutation tool: {selected_tool}")
            # Fall through to execute the tool

    # === Execute the Tool ===
    try:
        logger.info(f"Executing tool {selected_tool} with args: {tool_args}")

        # tool.coroutine 직접 호출 (_user_id는 스키마에 없어서 ainvoke로는 전달 불가)
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

        # Mutation 도구 실행 성공 시 hitl_status를 "executed"로 설정
        # 이렇게 하면 Evaluator가 replanning을 반환해도 Planning에서 HITL 재요청 방지
        is_mutation = tool_category_from_meta == ToolCategory.MUTATION.value
        new_hitl_status = "executed" if is_mutation else "none"

        return OrchestrationState(
            tool_results=tool_results,
            # Clear HITL state after successful execution (but mark as executed for mutations)
            hitl_status=new_hitl_status,
            hitl_tool_name=None,
            hitl_extracted_params=None,
            hitl_confirmation_message=None,
        )

    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return OrchestrationState(
            tool_results=f"도구 실행 중 오류가 발생했습니다: {str(e)}",
            hitl_status="none",
            hitl_tool_name=None,
            hitl_extracted_params=None,
            hitl_confirmation_message=None,
        )
