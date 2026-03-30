"""MIT Tool Decorators

Custom decorators for defining tools with HITL metadata.
"""

from enum import Enum
from typing import Callable

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, Field


class ToolCategory(str, Enum):
    """Tool category determines HITL behavior"""

    QUERY = "query"  # Read-only, no HITL required
    MUTATION = "mutation"  # Write operation, requires HITL in Spotlight mode


class ToolMode(str, Enum):
    """Tool availability mode"""

    VOICE = "voice"  # Voice mode (in-meeting assistant)
    SPOTLIGHT = "spotlight"  # Spotlight mode (standalone meeting manager)


# Registry for tools
_tools: dict[str, StructuredTool] = {}
_tool_metadata: dict[str, dict] = {}


def mit_tool(
    category: ToolCategory | str = ToolCategory.QUERY,
    modes: list[ToolMode] | None = None,
    display_template: str | None = None,
    hitl_fields: dict[str, dict] | None = None,
):
    """MIT Tool decorator with HITL metadata support.

    Args:
        category: Tool category (query or mutation)
        modes: List of modes where this tool is available.
               None means available in all modes.
               e.g., [ToolMode.SPOTLIGHT] = Spotlight only
        display_template: Natural language template for HITL confirmation.
                         Use {{param_name}} for input placeholders.
        hitl_fields: HITL field configuration for each parameter.
                    Example: {
                        "team_id": {
                            "input_type": "select",
                            "options_source": "user_teams",
                            "display_field": "name",
                            "placeholder": "팀을 선택하세요"
                        },
                        "scheduled_at": {
                            "input_type": "datetime"
                        }
                    }

    Example:
        @mit_tool(
            category="mutation",
            display_template="{{team_id}} 팀에 '{{title}}' 회의를 만들까요?",
            hitl_fields={
                "team_id": {"input_type": "select", "options_source": "user_teams"},
                "scheduled_at": {"input_type": "datetime"},
            }
        )
        async def create_meeting(team_id: str, title: str, scheduled_at: str) -> dict:
            '''새로운 회의를 생성합니다'''
            ...
    """

    def decorator(func: Callable) -> StructuredTool:
        # Apply LangChain @tool decorator
        lc_tool = tool(func)

        # Clova Studio API requires non-empty 'properties' in function call schema
        # If the tool has no parameters, create a wrapper with a dummy placeholder
        if lc_tool.args_schema:
            schema = lc_tool.args_schema.model_json_schema()
            if not schema.get("properties") or schema.get("properties") == {}:
                # Create a new schema with a placeholder field

                class PlaceholderSchema(BaseModel):
                    """Placeholder schema for tools with no parameters"""

                    # Clova Studio API requires at least one required field
                    # Using str without default makes it required in JSON Schema
                    placeholder: str = Field(
                        description="This parameter is not used (placeholder for API compatibility)",
                    )

                # Create a new StructuredTool with the patched schema
                lc_tool = StructuredTool(
                    name=lc_tool.name,
                    description=lc_tool.description,
                    func=lc_tool.func,
                    coroutine=lc_tool.coroutine,
                    args_schema=PlaceholderSchema,
                )

        # Normalize category
        cat = category if isinstance(category, ToolCategory) else ToolCategory(category)

        # Store metadata
        metadata = {
            "category": cat.value,
            "modes": [m.value for m in modes] if modes else None,
            "display_template": display_template,
            "hitl_fields": hitl_fields or {},
        }
        _tool_metadata[lc_tool.name] = metadata

        # Register tool
        _tools[lc_tool.name] = lc_tool

        return lc_tool

    return decorator


def get_tool(name: str) -> StructuredTool | None:
    """Get a tool by name"""
    return _tools.get(name)


def get_tool_metadata(name: str) -> dict | None:
    """Get HITL metadata for a tool"""
    return _tool_metadata.get(name)


def get_all_tools() -> list[StructuredTool]:
    """Get all registered tools"""
    return list(_tools.values())


def get_tools_by_category(category: ToolCategory | str) -> list[StructuredTool]:
    """Get tools by category"""
    cat = category if isinstance(category, str) else category.value
    return [
        tool for name, tool in _tools.items()
        if _tool_metadata.get(name, {}).get("category") == cat
    ]


def get_query_tools() -> list[StructuredTool]:
    """Get all query tools"""
    return get_tools_by_category(ToolCategory.QUERY)


def get_mutation_tools() -> list[StructuredTool]:
    """Get all mutation tools"""
    return get_tools_by_category(ToolCategory.MUTATION)


def is_mutation_tool(name: str) -> bool:
    """Check if a tool is a mutation tool"""
    metadata = _tool_metadata.get(name, {})
    return metadata.get("category") == ToolCategory.MUTATION.value


def get_tools_by_mode(mode: ToolMode | str) -> list[StructuredTool]:
    """Get tools available in a specific mode.

    Tools with modes=None are available in all modes.
    Tools with specific modes are only available in those modes.
    """
    mode_value = mode if isinstance(mode, str) else mode.value
    return [
        tool for name, tool in _tools.items()
        if _tool_metadata.get(name, {}).get("modes") is None
        or mode_value in _tool_metadata.get(name, {}).get("modes", [])
    ]


def clear_registry() -> None:
    """Clear all registered tools (for testing)"""
    global _tools, _tool_metadata
    _tools = {}
    _tool_metadata = {}
