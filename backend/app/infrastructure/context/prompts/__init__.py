"""Context Engineering Prompts Module

토픽 감지 및 요약 프롬프트 모듈
"""

from app.infrastructure.context.prompts.topic_detection import (
    TOPIC_CHANGE_KEYWORDS,
    TOPIC_DETECTION_PROMPT,
)
from app.infrastructure.context.prompts.summarization import (
    L1_SUMMARY_PROMPT,
)

__all__ = [
    "TOPIC_CHANGE_KEYWORDS",
    "TOPIC_DETECTION_PROMPT",
    "L1_SUMMARY_PROMPT",
]
