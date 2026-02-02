"""AI 에이전트 상수

멘션 가능한 AI 에이전트 목록 및 관련 상수
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AIAgent:
    """AI 에이전트 정의"""

    id: str
    name: str
    display_name: str
    mention: str
    description: str


# 멘션 가능한 AI 에이전트 목록
AI_AGENTS: list[AIAgent] = [
    AIAgent(
        id="11111111-1111-1111-1111-111111111111",  # PR #62 AGENT_USER_ID와 동일
        name="부덕이",
        display_name="부덕이",
        mention="@부덕이",
        description="이 결정 사항에 대해 궁금한 점이 있으면 언제든지 물어보세요!",
    ),
]

# 기본 AI 에이전트
DEFAULT_AI_AGENT = AI_AGENTS[0]

# 에이전트 멘션 패턴 (정규식)
# 모든 에이전트의 멘션을 매칭
AGENT_MENTION_PATTERN = re.compile(
    r"(" + "|".join(re.escape(agent.mention) for agent in AI_AGENTS) + r")\b",
    re.IGNORECASE,
)


def has_agent_mention(text: str) -> bool:
    """텍스트에 에이전트 멘션이 있는지 확인"""
    return AGENT_MENTION_PATTERN.search(text) is not None
