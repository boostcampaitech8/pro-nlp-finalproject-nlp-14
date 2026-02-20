"""generate_pr 라우팅 노드.

토큰 수와 토픽 수를 기준으로 라우팅:
- short: 짧은 회의 (토픽 1-2개 AND < 3K tokens) → single pass
- long: 긴 회의 (토픽 3개+ OR >= 3K tokens) → topic-aware chunked pass
"""

import logging

from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState

logger = logging.getLogger(__name__)

SHORT_THRESHOLD_TOKENS = 3000
SHORT_THRESHOLD_TOPICS = 3  # 이하면 single pass


def _count_tokens(text: str) -> int:
    """토큰 수를 실측한다. tiktoken 사용 불가 시 안전한 fallback 사용."""
    if not text:
        return 0

    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # 한글/영문 혼합에서 대략 1토큰 ~= 2~4자 범위.
        # 과소추정 방지를 위해 보수적으로 3자로 계산한다.
        return max(1, len(text) // 3)


async def route_by_token_count(state: GeneratePrState) -> GeneratePrState:
    """토큰 수와 토픽 수 기준으로 single/chunked 경로 결정.

    라우팅 규칙:
    - short: 토픽 <= 2개 AND 토큰 < 3000 → single pass
    - long: 토픽 >= 3개 OR 토큰 >= 3000 → chunked pass (topic-aware)
    """
    transcript_text = state.get("generate_pr_transcript_text", "")
    realtime_topics = state.get("generate_pr_realtime_topics", []) or []

    token_count = _count_tokens(transcript_text)
    topic_count = len(realtime_topics)

    # 토픽이 많거나 토큰이 많으면 chunked pass
    is_long_by_tokens = token_count >= SHORT_THRESHOLD_TOKENS
    is_long_by_topics = topic_count > SHORT_THRESHOLD_TOPICS

    if is_long_by_tokens or is_long_by_topics:
        route = "long"
    else:
        route = "short"

    logger.info(
        "generate_pr route selected: route=%s, tokens=%d (threshold=%d), topics=%d (threshold=%d)",
        route,
        token_count,
        SHORT_THRESHOLD_TOKENS,
        topic_count,
        SHORT_THRESHOLD_TOPICS,
    )

    return GeneratePrState(generate_pr_route=route)
