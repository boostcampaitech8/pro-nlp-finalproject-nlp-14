"""Tool Registry for MIT Orchestration

Simplified registry that provides separate tool access for Voice and Spotlight modes.

Voice orchestration uses get_query_tools()
Spotlight orchestration uses get_all_tools()
"""

import logging

from langchain_core.tools import StructuredTool

from .decorators import (
    ToolCategory,
    ToolMode,
    get_all_tools,
    get_mutation_tools,
    get_query_tools,
    get_tool,
    get_tool_metadata,
    get_tools_by_mode,
    is_mutation_tool,
)

logger = logging.getLogger(__name__)


def get_tool_by_name(name: str) -> StructuredTool | None:
    """Get a tool by its name

    Args:
        name: Tool name

    Returns:
        StructuredTool or None if not found
    """
    return get_tool(name)


def get_tool_category(name: str) -> str | None:
    """Get tool category by name

    Args:
        name: Tool name

    Returns:
        Category string ('query' or 'mutation') or None
    """
    metadata = get_tool_metadata(name)
    return metadata.get("category") if metadata else None


def get_voice_tools() -> list:
    """Get tools available in Voice mode"""
    return get_tools_by_mode(ToolMode.VOICE)


def get_spotlight_tools() -> list:
    """Get tools available in Spotlight mode"""
    return get_tools_by_mode(ToolMode.SPOTLIGHT)


# Re-export from decorators
__all__ = [
    "ToolCategory",
    "ToolMode",
    "get_query_tools",
    "get_all_tools",
    "get_mutation_tools",
    "get_tools_by_mode",
    "get_voice_tools",
    "get_spotlight_tools",
    "get_tool_by_name",
    "get_tool_category",
    "get_tool_metadata",
    "is_mutation_tool",
]

