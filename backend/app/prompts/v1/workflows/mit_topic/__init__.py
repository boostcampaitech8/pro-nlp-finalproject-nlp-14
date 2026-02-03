"""MIT Topic 워크플로우 프롬프트"""

from .merging import (
    TOPIC_MERGE_PROMPT,
    TOPIC_MERGE_SCHEMA,
    TOPIC_NAME_MERGE_PROMPT,
)
from .separation import (
    RECURSIVE_TOPIC_SEPARATION_PROMPT,
    TOPIC_SEPARATION_PROMPT,
    VERSION,
)

__all__ = [
    "VERSION",
    # Merging
    "TOPIC_MERGE_PROMPT",
    "TOPIC_MERGE_SCHEMA",
    "TOPIC_NAME_MERGE_PROMPT",
    # Separation
    "TOPIC_SEPARATION_PROMPT",
    "RECURSIVE_TOPIC_SEPARATION_PROMPT",
]
