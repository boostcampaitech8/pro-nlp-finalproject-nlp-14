"""Tool Registry for MIT Orchestration

Simplified registry that provides separate tool access for Voice and Spotlight modes.

Voice orchestration uses get_query_tools()
Spotlight orchestration uses get_all_tools()
"""

import logging

from langchain_core.tools import StructuredTool

from .decorators import (
    ToolCategory,
    get_all_tools,
    get_mutation_tools,
    get_query_tools,
    get_tool,
    get_tool_metadata,
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


# Re-export from decorators
__all__ = [
    "ToolCategory",
    "get_query_tools",
    "get_all_tools",
    "get_mutation_tools",
    "get_tool_by_name",
    "get_tool_category",
    "get_tool_metadata",
    "is_mutation_tool",
]

