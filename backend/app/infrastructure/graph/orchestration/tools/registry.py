"""Tool Registry for MIT Orchestration

This module provides a mode-aware tool registry that returns
different tool sets based on interaction mode (Voice vs Spotlight).

Uses the decorators module for actual tool storage.
"""

import logging
from enum import Enum

from langchain_core.tools import StructuredTool

from .decorators import (
    get_all_tools,
    get_query_tools,
    get_mutation_tools,
    get_tool,
    get_tool_metadata,
    is_mutation_tool,
    ToolCategory,
)

logger = logging.getLogger(__name__)


class InteractionMode(str, Enum):
    """Interaction mode determines available tools"""

    VOICE = "voice"  # Query tools only
    SPOTLIGHT = "spotlight"  # Query + Mutation tools


def get_tools_for_mode(mode: InteractionMode) -> list[StructuredTool]:
    """Get available tools based on interaction mode

    Args:
        mode: InteractionMode (VOICE or SPOTLIGHT)

    Returns:
        list[StructuredTool]: List of tools available in the given mode
    """
    if mode == InteractionMode.VOICE:
        # Voice mode: only query tools
        return get_query_tools()
    elif mode == InteractionMode.SPOTLIGHT:
        # Spotlight mode: all tools (query + mutation)
        return get_all_tools()
    return []


def get_langchain_tools_for_mode(mode: InteractionMode) -> list[StructuredTool]:
    """Get LangChain StructuredTools for bind_tools based on interaction mode

    Args:
        mode: InteractionMode (VOICE or SPOTLIGHT)

    Returns:
        list[StructuredTool]: LangChain tools for bind_tools
    """
    # Tools from @mit_tool are already StructuredTools
    return get_tools_for_mode(mode)


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


# Re-export from decorators for backward compatibility
__all__ = [
    "InteractionMode",
    "ToolCategory",
    "get_tools_for_mode",
    "get_langchain_tools_for_mode",
    "get_tool_by_name",
    "get_tool_category",
    "get_tool_metadata",
    "is_mutation_tool",
]
