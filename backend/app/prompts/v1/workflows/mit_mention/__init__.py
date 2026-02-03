"""MIT Mention 워크플로우 프롬프트"""

from .generation import (
    DOMAIN_KNOWLEDGE,
    FEW_SHOT_EXAMPLES,
    MENTION_RESPONSE_PROMPT,
    PERSONA,
    VERSION,
)

__all__ = [
    "VERSION",
    # Generation
    "PERSONA",
    "DOMAIN_KNOWLEDGE",
    "FEW_SHOT_EXAMPLES",
    "MENTION_RESPONSE_PROMPT",
]
