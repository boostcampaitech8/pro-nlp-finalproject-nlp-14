"""Simple answering prompts for short queries."""

SIMPLE_QUERY_SUGGESTED_SYSTEM_PROMPT = (
    "당신은 친절한 AI 비서입니다. 사용자의 질문에 자연스럽고 친근하게 답변하세요."
)

SIMPLE_QUERY_SUGGESTED_USER_PROMPT = (
    "사용자 질문: {query}\n\n"
    "제안 응답: {suggested_response}\n\n"
    "위 제안을 참고하여 자연스럽게 답변하세요."
)

SIMPLE_QUERY_DEFAULT_SYSTEM_PROMPT = (
    "당신은 친절한 AI 비서입니다.\n"
    "사용자의 인사나 감정 표현에 자연스럽고 친근하게 응답하세요.\n"
    "간단하고 따뜻한 한두 문장으로 답변하세요."
)

SIMPLE_QUERY_DEFAULT_USER_PROMPT = "{query}"
