"""Context Engineering Prompts Module

토픽 분할/병합 프롬프트 모음.
"""

from .topic_merging import (
    TOPIC_MERGE_PROMPT,
    TOPIC_MERGE_SCHEMA,
    TOPIC_NAME_MERGE_PROMPT,
)
from .topic_separation import (
    RECURSIVE_TOPIC_SEPARATION_PROMPT,
    TOPIC_SEPARATION_PROMPT,
)

__all__ = [
    "TOPIC_MERGE_PROMPT",
    "TOPIC_MERGE_SCHEMA",
    "TOPIC_NAME_MERGE_PROMPT",
    "TOPIC_SEPARATION_PROMPT",
    "RECURSIVE_TOPIC_SEPARATION_PROMPT",
]
