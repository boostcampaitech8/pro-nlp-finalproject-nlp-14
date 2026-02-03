"""새 Decision 생성 노드"""

import json
import logging

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_decision_generator_llm
from app.infrastructure.graph.workflows.mit_suggestion.state import (
    MitSuggestionState,
)
from app.prompts.v1.workflows.mit_suggestion import (
    CONFIDENCE_LEVELS,
    DECISION_GENERATION_HUMAN,
    DECISION_GENERATION_SYSTEM,
    DEFAULT_CONFIDENCE,
)

logger = logging.getLogger(__name__)


# 프롬프트 템플릿 (prompts/v1/workflows/suggestion.py에서 import)
DECISION_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", DECISION_GENERATION_SYSTEM),
    ("human", DECISION_GENERATION_HUMAN),
])


async def generate_new_decision(state: MitSuggestionState) -> dict:
    """Suggestion을 반영하여 새로운 Decision 내용 생성

    Contract:
        reads: mit_suggestion_content, mit_suggestion_decision_content,
               mit_suggestion_decision_context, mit_suggestion_agenda_topic,
               mit_suggestion_gathered_context
        writes: mit_suggestion_new_decision_content, mit_suggestion_supersedes_reason,
                mit_suggestion_confidence
        side-effects: LLM API 호출
        failures: GENERATION_FAILED -> 원본 Decision 내용 유지 + low confidence
    """
    suggestion_content = state.get("mit_suggestion_content", "")
    decision_content = state.get("mit_suggestion_decision_content", "")
    decision_context = state.get("mit_suggestion_decision_context") or ""
    agenda_topic = state.get("mit_suggestion_agenda_topic") or "안건 정보 없음"
    gathered_context = state.get("mit_suggestion_gathered_context") or {}

    # 회의 정보 섹션 구성
    meeting_section = ""
    if gathered_context.get("meeting_context"):
        mc = gathered_context["meeting_context"]
        meeting_parts = []
        if mc.get("meeting_title"):
            meeting_parts.append(f"- 회의 제목: {mc['meeting_title']}")
        if mc.get("agenda_topics"):
            topics = ", ".join(mc["agenda_topics"][:5])  # 최대 5개
            meeting_parts.append(f"- 전체 안건: {topics}")
        if meeting_parts:
            meeting_section = "[회의 정보]\n" + "\n".join(meeting_parts)

    # 기존 논의 내용 섹션 구성
    thread_section = ""
    if gathered_context.get("thread_history"):
        thread_items = []
        for h in gathered_context["thread_history"][-5:]:  # 최근 5개
            author = h.get("author", "Unknown")
            content = h.get("content", "")[:100]
            thread_items.append(f"- {author}: {content}...")
        if thread_items:
            thread_section = "[기존 논의 내용]\n" + "\n".join(thread_items)

    # 관련 결정사항 섹션 구성
    sibling_section = ""
    if gathered_context.get("sibling_decisions"):
        sibling_items = []
        for d in gathered_context["sibling_decisions"][:3]:  # 최대 3개
            content = d.get("content", "")[:100]
            status = d.get("status", "unknown")
            sibling_items.append(f"- [{status}] {content}...")
        if sibling_items:
            sibling_section = "[관련 결정사항 (같은 안건)]\n" + "\n".join(sibling_items)

    try:
        llm = get_decision_generator_llm()
        chain = DECISION_GENERATION_PROMPT | llm

        result = await chain.ainvoke({
            "meeting_section": meeting_section if meeting_section else "[회의 정보]\n정보 없음",
            "agenda_topic": agenda_topic,
            "decision_content": decision_content,
            "decision_context": decision_context if decision_context else "맥락 정보 없음",
            "thread_section": thread_section if thread_section else "[기존 논의 내용]\n논의 내역 없음",
            "sibling_section": sibling_section if sibling_section else "",
            "suggestion_content": suggestion_content,
        })

        response_text = result.content if hasattr(result, 'content') else str(result)

        # JSON 파싱 시도
        try:
            # JSON 블록 추출 (```json ... ``` 또는 순수 JSON)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            parsed = json.loads(json_str)

            new_content = parsed.get("new_decision_content")
            reason = parsed.get("supersedes_reason")
            confidence = parsed.get("confidence")

            # H2: Validate and log when fallback values are used
            if not new_content:
                logger.warning(
                    "[generate_new_decision] Missing new_decision_content in response, "
                    "using original decision content as fallback"
                )
                new_content = decision_content
            if not reason:
                logger.info("[generate_new_decision] Missing supersedes_reason, using default")
                reason = "사용자 제안 반영"
            if not confidence:
                logger.info("[generate_new_decision] Missing confidence, using default")
                confidence = DEFAULT_CONFIDENCE

            # confidence 값 검증
            if confidence not in CONFIDENCE_LEVELS:
                confidence = DEFAULT_CONFIDENCE

            logger.info(
                f"[generate_new_decision] Generated: "
                f"confidence={confidence}, content_len={len(new_content)}"
            )

            return {
                "mit_suggestion_new_decision_content": new_content,
                "mit_suggestion_supersedes_reason": reason,
                "mit_suggestion_confidence": confidence,
            }

        except json.JSONDecodeError as e:
            logger.warning(f"[generate_new_decision] JSON parse failed: {e}")
            # JSON 파싱 실패 시 원본 응답을 Decision으로 사용
            return {
                "mit_suggestion_new_decision_content": response_text[:500],
                "mit_suggestion_supersedes_reason": "사용자 제안 반영 (AI 응답 파싱 실패)",
                "mit_suggestion_confidence": "low",
            }

    except Exception:
        logger.exception("[generate_new_decision] LLM call failed")
        # 에러 발생 시 원본 Decision 유지
        return {
            "mit_suggestion_new_decision_content": decision_content,
            "mit_suggestion_supersedes_reason": "AI 생성 중 오류가 발생했습니다",
            "mit_suggestion_confidence": "low",
        }
