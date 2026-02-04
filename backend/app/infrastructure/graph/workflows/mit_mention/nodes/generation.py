"""응답 생성 노드"""

import logging

from app.infrastructure.graph.integration.llm import get_mention_generator_llm
from app.infrastructure.graph.workflows.mit_mention.state import (
    MitMentionState,
)
from app.prompts.v1.workflows.mit_mention import MENTION_RESPONSE_PROMPT

logger = logging.getLogger(__name__)


async def generate_response(state: MitMentionState) -> dict:
    """멘션에 대한 AI 응답 생성

    Contract:
        reads: mit_mention_content, mit_mention_gathered_context, mit_mention_retry_reason,
               mit_mention_search_results
        writes: mit_mention_raw_response
        side-effects: LLM API 호출
        failures: GENERATION_FAILED -> 기본 응답 반환
    """
    content = state.get("mit_mention_content", "")
    gathered_context = state.get("mit_mention_gathered_context") or {}
    retry_reason = state.get("mit_mention_retry_reason")
    retry_count = state.get("mit_mention_retry_count", 0)
    search_results = state.get("mit_mention_search_results") or []

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
                meeting_parts.append(f"**회의의 다른 결정사항**:\n" + "\n".join(decisions_summary))

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
    if search_results:
        search_items = []
        for i, result in enumerate(search_results[:5], 1):
            result_type = result.get("type", "Unknown")
            title = result.get("title", "제목 없음")
            content_preview = result.get("content", "")[:100]
            score = result.get("score", 0)

            search_items.append(
                f"{i}. [{result_type}] {title} (관련도: {score:.2f})\n"
                f"   {content_preview}..."
            )

        if search_items:
            search_section = "[관련 지식]\n" + "\n".join(search_items)
            logger.info(f"[generate_response] Added {len(search_items)} search results to context")

    # 재시도 섹션 구성
    retry_section = ""
    if retry_reason and retry_count > 0:
        retry_section = f"[이전 응답 문제점]\n{retry_reason}\n위 문제를 개선하여 다시 답변하세요."

    try:
        llm = get_mention_generator_llm()

        chain = MENTION_RESPONSE_PROMPT | llm

        result = await chain.ainvoke({
            "decision_content": gathered_context.get("decision_summary", ""),
            "context_section": context_section,
            "meeting_section": meeting_section,
            "history_section": history_section,
            "search_section": search_section,
            "retry_section": retry_section,
            "user_question": content,
        })

        response = result.content if hasattr(result, 'content') else str(result)

        logger.info(f"[generate_response] Response generated: {len(response)} chars")

        return {"mit_mention_raw_response": response}

    except Exception as _:
        logger.exception("[generate_response] LLM call failed")
        fallback = (
            "죄송합니다, 응답을 생성하는 중 오류가 발생했습니다. "
            "잠시 후 다시 시도해 주세요."
        )
        return {"mit_mention_raw_response": fallback}
