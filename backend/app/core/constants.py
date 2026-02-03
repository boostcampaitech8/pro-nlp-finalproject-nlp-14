"""Application constants and configuration values"""

from uuid import UUID

# System User (Agent)
AGENT_USER_ID = UUID("11111111-1111-1111-1111-111111111111")

# File upload limits
MAX_RECORDING_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# URL expiration
PRESIGNED_URL_EXPIRATION = 3600  # 1 hour in seconds

# Recording formats
SUPPORTED_RECORDING_FORMATS = ["webm", "mp4", "mkv"]
DEFAULT_RECORDING_FORMAT = "webm"

# M3: Decision status constants
class DecisionStatus:
    """Decision 상태 상수"""
    DRAFT = "draft"
    LATEST = "latest"
    APPROVED = "approved"
    REJECTED = "rejected"
    OUTDATED = "outdated"
    SUPERSEDED = "superseded"

    # Finalized statuses (cannot be modified)
    FINALIZED_STATUSES = [REJECTED, OUTDATED, SUPERSEDED, LATEST]

# Suggestion status constants
class SuggestionStatus:
    """Suggestion 상태 상수"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
