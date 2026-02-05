"""응답 생성 노드"""

import logging

from app.infrastructure.graph.integration.llm import get_mention_generator_llm
from app.infrastructure.graph.workflows.mit_mention.state import (
    MitMentionState,
)
from app.prompts.v1.workflows.mit_mention import MENTION_RESPONSE_PROMPT

logger = logging.getLogger(__name__)


def _is_capability_question(content: str) -> bool:
    if not content:
        return False

    keywords = [
        "할 수 있는", "할수있는", "가능한", "뭐 할 수", "무엇을 할 수",
        "어떤 기능", "기능 알려", "기능 소개", "어떤 도움", "도와줄 수",
        "무슨 일", "무엇을 해", "무엇을 하", "도움이 되는",
    ]

    return any(k in content for k in keywords)


async def generate_response(state: MitMentionState) -> dict:
    """멘션에 대한 AI 응답 생성

    Contract:
        reads: mit_mention_content, mit_mention_gathered_context, mit_mention_retry_reason
        writes: mit_mention_raw_response
        side-effects: LLM API 호출
        failures: GENERATION_FAILED -> 기본 응답 반환
    """
    content = state.get("mit_mention_content", "")
    gathered_context = state.get("mit_mention_gathered_context") or {}
    retry_reason = state.get("mit_mention_retry_reason")
    retry_count = state.get("mit_mention_retry_count", 0)
    is_capability_question = _is_capability_question(content)

    # 컨텍스트 섹션 구성
    context_section = ""
    if gathered_context.get("decision_context"):
        context_section = f"[결정 배경]\n{gathered_context['decision_context']}"

    # 회의 정보 섹션 구성
    meeting_section = ""
    if gathered_context.get("meeting_context"):
        mc = gathered_context["meeting_context"]
        meeting_parts = []

        if mc.get("meeting_title"):
            meeting_parts.append(f"**회의 제목**: {mc['meeting_title']}")

        if mc.get("agenda_topics"):
            topics = ", ".join(mc["agenda_topics"])
            meeting_parts.append(f"**논의된 안건**: {topics}")

        if mc.get("other_decisions"):
            decisions_summary = []
            for i, d in enumerate(mc["other_decisions"][:3], 1):  # 최대 3개만 표시
                content_preview = d["content"][:100] + "..." if len(d["content"]) > 100 else d["content"]
                decisions_summary.append(f"{i}. {content_preview}")
            if decisions_summary:
                meeting_parts.append("**회의의 다른 결정사항**:\n" + "\n".join(decisions_summary))

        if meeting_parts:
            meeting_section = "[회의 정보]\n" + "\n".join(meeting_parts)

    # 대화 이력 섹션 구성
    history_section = ""
    if gathered_context.get("conversation_history"):
        history_items = []
        for h in gathered_context["conversation_history"]:
            role = "사용자" if h["role"] == "user" else "AI"
            history_items.append(f"- {role}: {h['content'][:100]}...")
        history_section = "[이전 대화]\n" + "\n".join(history_items)

    # 검색 결과 섹션 구성
    search_section = ""
    if gathered_context.get("search_results"):
        search_section = gathered_context["search_results"]

    # 재시도 섹션 구성
    retry_section = ""
    if retry_reason and retry_count > 0:
        retry_section = f"[이전 응답 문제점]\n{retry_reason}\n위 문제를 개선하여 다시 답변하세요."

    # 기능 안내 섹션 구성
    capability_section = ""
    if is_capability_question:
        capability_section = (
            "[기능 안내 강화]\n"
            "사용자가 가능한 도움을 묻고 있습니다. 충분히 길고 자세한 안내를 제공하세요.\n"
            "- 핵심 기능 5개 이상을 항목으로 제시\n"
            "- 예시 질문 3개 이상 포함\n"
            "- 추가로 필요한 정보를 묻는 한 줄 질문 포함"
        )

    try:
        llm = get_mention_generator_llm()

        chain = MENTION_RESPONSE_PROMPT | llm

        # 입력 프롬프트 계산
        prompt_parts = {
            "decision_content": gathered_context.get("decision_summary", ""),
            "context_section": context_section,
            "meeting_section": meeting_section,
            "history_section": history_section,
            "search_section": search_section,
            "retry_section": retry_section,
            "capability_section": capability_section,
            "user_question": content,
        }
        prompt_size = sum(len(str(v)) for v in prompt_parts.values())

        result = await chain.ainvoke(prompt_parts)

        response = result.content if hasattr(result, 'content') else str(result)

        # 상세 로깅: 입력과 출력 크기 추적
        logger.info(
            f"[generate_response] Generated response | "
            f"prompt_size={prompt_size} chars, "
            f"response_size={len(response)} chars, "
            f"retry_count={retry_count}"
        )
        # 응답이 불완전하게 끝났는지 추가 로깅
        if response and not response.rstrip().endswith(("다.", "요.", "군요.", "습니다.", "렇습니다.", "세요.")):
            logger.warning(
                f"[generate_response] Response may be incomplete | "
                f"last_50_chars={response[-50:] if len(response) >= 50 else response}"
            )

        return {"mit_mention_raw_response": response}

    except Exception as _:
        logger.exception("[generate_response] LLM call failed")
        fallback = (
            "죄송합니다, 응답을 생성하는 중 오류가 발생했습니다. "
            "잠시 후 다시 시도해 주세요."
        )
        return {"mit_mention_raw_response": fallback}
