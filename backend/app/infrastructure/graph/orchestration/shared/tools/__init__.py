"""MIT Orchestration Tools Package

This package contains tool definitions for the MIT orchestration system.
Tools are divided into two categories:
- Query Tools: Read-only operations (available in both Voice and Spotlight modes)
- Mutation Tools: Write operations (Spotlight mode only, requires HITL confirmation)

Tools are defined using @mit_tool decorator for automatic registration.
"""

from .decorators import (
    ToolCategory,
    mit_tool,
    get_tool,
    get_tool_metadata,
    get_all_tools,
    get_query_tools,
    get_mutation_tools,
    is_mutation_tool,
)

# Import tool modules to trigger registration
# Query tools (available in both Voice and Spotlight modes)
from . import query  # noqa: F401

# Mutation tools (Spotlight mode only)
from . import mutation  # noqa: F401

__all__ = [
    "ToolCategory",
    "mit_tool",
    "get_tool",
    "get_tool_metadata",
    "get_all_tools",
    "get_query_tools",
    "get_mutation_tools",
    "is_mutation_tool",
]
