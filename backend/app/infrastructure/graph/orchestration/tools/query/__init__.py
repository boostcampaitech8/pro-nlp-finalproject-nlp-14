"""Query Tools for MIT Orchestration

Query tools are read-only operations that do not require HITL confirmation.
Available in both Voice and Spotlight modes.

Tools are auto-registered via @mit_tool decorator on import.
"""

# Import tool modules to trigger registration
from . import meeting_tools  # noqa: F401
from . import team_tools  # noqa: F401
from . import utility_tools  # noqa: F401

# Export function names for reference
__all__ = [
    # Meeting tools
    "get_meetings",
    "get_meeting",
    # Team tools
    "get_my_teams",
    "get_team",
    "get_team_members",
    # Utility tools
    "get_current_datetime",
    "get_user_profile",
    "get_upcoming_meetings",
    "get_meeting_transcript",
    "get_meeting_summary",
]
