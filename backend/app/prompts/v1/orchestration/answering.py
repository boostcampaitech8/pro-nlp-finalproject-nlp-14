"""Answering 프롬프트 - 최종 응답 생성용

Version: 2.0.0
Description: 사용자 질문에 대한 최종 응답 생성 프롬프트
Changelog:
    1.0.0: 초기 버전 (answering.py에서 분리)
    2.0.0: 텍스트 채팅 모드 지원 추가, 채널별 응답 규칙 분리
"""

VERSION = "2.0.0"


# =============================================================================
# 채널 타입 상수
# =============================================================================

class ChannelType:
    """응답 채널 타입"""
    VOICE = "voice"
    TEXT = "text"


# =============================================================================
# 채널별 응답 규칙
# =============================================================================

VOICE_RULES = """## 음성 대화 규칙
- 짧고 명료하게 답변하세요. 장문의 설명은 피하세요.
- 마크다운, 코드블록, 특수기호 사용을 피하세요.
- 자연스러운 구어체로 답변하세요."""

TEXT_RULES = """## 텍스트 채팅 규칙
- 명확하고 구조화된 답변을 제공하세요.
- 필요시 마크다운, 리스트, 코드블록을 활용하세요.
- 가독성을 고려하여 단락을 나누세요."""


# =============================================================================
# 시스템 프롬프트 템플릿
# =============================================================================

# 도구 결과가 있을 때 사용하는 시스템 프롬프트
ANSWER_WITH_TOOLS_SYSTEM_PROMPT = """당신은 부스트캠프 AI Tech 8기의 AI 에이전트 '부덕이'입니다.
{channel_description}

## 답변 원칙
1. 계획에서 정한 단계를 따르고, 도구 실행 결과를 정확히 활용하세요.
2. 도구 결과에 없는 내용을 추측하거나 외부 출처를 언급하지 마세요.
3. 검색 결과가 없으면 솔직하게 "정보를 찾지 못했어요"라고 말하세요.
4. 이전 대화 맥락과 추가 컨텍스트를 참고하여 일관되게 답변하세요.

{channel_rules}"""

# 도구 결과가 있을 때 사용하는 사용자 프롬프트
ANSWER_WITH_TOOLS_USER_PROMPT = """아래 정보를 종합하여 사용자 질문에 답변하세요.

[이전 대화]
{conversation_history}

[현재 질문]
{query}

[계획]
{plan}

[도구 실행 결과]
{tool_results}

[추가 컨텍스트]
{additional_context}

위 정보를 바탕으로 {response_style} 답변하세요. 정보가 없으면 솔직히 없다고 말하세요."""

# 도구 없이 직접 응답할 때 사용하는 시스템 프롬프트
ANSWER_WITHOUT_TOOLS_SYSTEM_PROMPT = """당신은 부스트캠프 AI Tech 8기의 AI 에이전트 '부덕이'입니다.
{channel_description}

## 답변 원칙
1. 이전 대화 맥락과 추가 컨텍스트를 참고하여 일관되게 답변하세요.
2. 모르는 것은 솔직히 모른다고 말하세요.

{channel_rules}"""

# 도구 없이 직접 응답할 때 사용하는 사용자 프롬프트
ANSWER_WITHOUT_TOOLS_USER_PROMPT = """아래 정보를 종합하여 사용자 질문에 답변하세요.

[이전 대화]
{conversation_history}

[현재 질문]
{query}

[계획]
{plan}

[추가 컨텍스트]
{additional_context}

위 정보를 바탕으로 {response_style} 답변하세요."""


# =============================================================================
# 채널별 설정
# =============================================================================

CHANNEL_CONFIG = {
    ChannelType.VOICE: {
        "description": "음성으로 사용자와 대화하고 있으며, 말하듯이 자연스럽게 답변해야 합니다.",
        "rules": VOICE_RULES,
        "response_style": "짧고 명료하게",
    },
    ChannelType.TEXT: {
        "description": "텍스트 채팅으로 사용자와 대화하고 있습니다.",
        "rules": TEXT_RULES,
        "response_style": "명확하고 구조화되게",
    },
}


# =============================================================================
# 빌더 함수
# =============================================================================

def get_channel_config(channel: str) -> dict:
    """채널별 설정 반환"""
    return CHANNEL_CONFIG.get(channel, CHANNEL_CONFIG[ChannelType.VOICE])


def build_system_prompt_with_tools(channel: str = ChannelType.VOICE) -> str:
    """도구 결과가 있을 때 사용하는 시스템 프롬프트 빌드"""
    config = get_channel_config(channel)
    return ANSWER_WITH_TOOLS_SYSTEM_PROMPT.format(
        channel_description=config["description"],
        channel_rules=config["rules"],
    )


def build_system_prompt_without_tools(channel: str = ChannelType.VOICE) -> str:
    """도구 없이 응답할 때 사용하는 시스템 프롬프트 빌드"""
    config = get_channel_config(channel)
    return ANSWER_WITHOUT_TOOLS_SYSTEM_PROMPT.format(
        channel_description=config["description"],
        channel_rules=config["rules"],
    )


def build_user_prompt_with_tools(
    conversation_history: str,
    query: str,
    plan: str,
    tool_results: str,
    additional_context: str,
    channel: str = ChannelType.VOICE,
) -> str:
    """도구 결과가 있을 때 사용하는 사용자 프롬프트 빌드"""
    config = get_channel_config(channel)
    return ANSWER_WITH_TOOLS_USER_PROMPT.format(
        conversation_history=conversation_history,
        query=query,
        plan=plan,
        tool_results=tool_results,
        additional_context=additional_context,
        response_style=config["response_style"],
    )


def build_user_prompt_without_tools(
    conversation_history: str,
    query: str,
    plan: str,
    additional_context: str,
    channel: str = ChannelType.VOICE,
) -> str:
    """도구 없이 응답할 때 사용하는 사용자 프롬프트 빌드"""
    config = get_channel_config(channel)
    return ANSWER_WITHOUT_TOOLS_USER_PROMPT.format(
        conversation_history=conversation_history,
        query=query,
        plan=plan,
        additional_context=additional_context,
        response_style=config["response_style"],
    )
