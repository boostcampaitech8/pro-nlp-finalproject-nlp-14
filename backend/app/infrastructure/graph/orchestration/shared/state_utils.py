"""Shared State Utilities for Orchestration"""

RESET_TOOL_RESULTS = "__CLEAR_TOOL_RESULTS__"


def tool_results_reducer(current: str | None, new: str | None) -> str:
    """tool_results 누적/리셋을 위한 reducer."""
    if new == RESET_TOOL_RESULTS:
        return ""
    if current is None:
        current = ""
    if new is None:
        return current
    separator = "\n---\n" if current else ""
    return current + separator + new
