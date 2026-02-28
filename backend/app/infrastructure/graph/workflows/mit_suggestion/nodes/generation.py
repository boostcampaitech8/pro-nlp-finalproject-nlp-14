"""새 Decision 생성 노드"""

import json
import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_decision_generator_llm
from app.infrastructure.graph.workflows.mit_suggestion.state import (
    MitSuggestionState,
)
from app.prompt.v1.workflows.mit_suggestion import (
    CONFIDENCE_LEVELS,
    DECISION_GENERATION_HUMAN,
    DECISION_GENERATION_SYSTEM,
    DEFAULT_CONFIDENCE,
)

logger = logging.getLogger(__name__)


# 프롬프트 템플릿 (app.prompt.v1.workflows.mit_suggestion에서 import)
DECISION_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", DECISION_GENERATION_SYSTEM),
    ("human", DECISION_GENERATION_HUMAN),
])


def _format_span_ref(span: dict[str, Any]) -> str:
    """SpanRef dict를 프롬프트용 단일 라인으로 포맷한다. (fallback용)"""
    transcript_id = span.get("transcript_id", "meeting-transcript")
    start_utt = span.get("start_utt_id")
    end_utt = span.get("end_utt_id")
    if start_utt and end_utt:
        utt_range = f"{start_utt}~{end_utt}"
    else:
        utt_range = start_utt or end_utt or "unknown"

    parts = [f"{transcript_id}:{utt_range}"]
    if span.get("topic_name"):
        parts.append(f"topic={span['topic_name']}")
    if span.get("start_ms") is not None and span.get("end_ms") is not None:
        parts.append(f"{span['start_ms']}ms~{span['end_ms']}ms")
    return " | ".join(parts)


def _format_evidence_text(evidence_text: dict[str, Any]) -> str:
    """evidence_text dict를 프롬프트용 문자열로 포맷한다.

    포맷:
        📍 근거 (2:30~3:20) [토픽명]
        (앞 컨텍스트)
        - 김철수: 발화 내용...
        ▶ 근거 발화
        - 박민수: 핵심 발화 내용...
        (뒤 컨텍스트)
        - 이영희: 발화 내용...
    """
    lines: list[str] = []

    # 헤더
    time_range = evidence_text.get("time_range", "")
    topic_name = evidence_text.get("topic_name")
    header = f"📍 근거 ({time_range})"
    if topic_name:
        header += f" [{topic_name}]"
    lines.append(header)

    # 앞 컨텍스트
    before_context = evidence_text.get("before_context", [])
    if before_context:
        lines.append("  (앞 컨텍스트)")
        for utt in before_context[-3:]:  # 최대 3개
            speaker = utt.get("speaker", "Unknown")
            text = utt.get("text", "")[:80]
            lines.append(f"  - {speaker}: {text}")

    # 근거 발화
    evidence_utterances = evidence_text.get("evidence_utterances", [])
    if evidence_utterances:
        lines.append("  ▶ 근거 발화")
        for utt in evidence_utterances[:5]:  # 최대 5개
            speaker = utt.get("speaker", "Unknown")
            text = utt.get("text", "")[:150]
            lines.append(f"  - {speaker}: {text}")

    # 뒤 컨텍스트
    after_context = evidence_text.get("after_context", [])
    if after_context:
        lines.append("  (뒤 컨텍스트)")
        for utt in after_context[:3]:  # 최대 3개
            speaker = utt.get("speaker", "Unknown")
            text = utt.get("text", "")[:80]
            lines.append(f"  - {speaker}: {text}")

    return "\n".join(lines)


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
    if gathered_context.get("agenda_topic"):
        agenda_topic = gathered_context.get("agenda_topic")

    # 회의 정보 섹션 구성
    meeting_section = ""
    if gathered_context.get("meeting_context"):
        mc = gathered_context["meeting_context"]
        meeting_parts = []
        if mc.get("meeting_title"):
            meeting_parts.append(f"- 회의 제목: {mc['meeting_title']}")
        if mc.get("meeting_date"):
            meeting_parts.append(f"- 회의 날짜: {mc['meeting_date']}")
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

    # 근거 섹션 구성 (실제 텍스트 우선, 없으면 SpanRef 메타데이터 fallback)
    evidence_parts: list[str] = []

    # 1. 원본 결정사항 근거
    decision_evidence_texts = gathered_context.get("decision_evidence_texts") or []
    decision_evidence = gathered_context.get("decision_evidence") or []

    if decision_evidence_texts:
        # 실제 발화 텍스트가 있는 경우
        evidence_parts.append("[원본 결정사항 근거]")
        for et in decision_evidence_texts[:3]:  # 최대 3개
            evidence_parts.append(_format_evidence_text(et))
    elif decision_evidence:
        # fallback: SpanRef 메타데이터만
        evidence_parts.append("[원본 결정사항 근거 SpanRef]")
        evidence_parts.extend(
            f"- {_format_span_ref(span)}" for span in decision_evidence[:8]
        )

    # 2. 안건 근거
    agenda_evidence_texts = gathered_context.get("agenda_evidence_texts") or []
    agenda_evidence = gathered_context.get("agenda_evidence") or []

    if agenda_evidence_texts:
        evidence_parts.append("\n[안건 근거]")
        for et in agenda_evidence_texts[:2]:  # 최대 2개
            evidence_parts.append(_format_evidence_text(et))
    elif agenda_evidence:
        evidence_parts.append("[안건 근거 SpanRef]")
        evidence_parts.extend(
            f"- {_format_span_ref(span)}" for span in agenda_evidence[:5]
        )

    # 3. 관련 결정사항 근거 (SpanRef만 - 텍스트 추출 미지원)
    sibling_evidence_lines: list[str] = []
    for sibling in (gathered_context.get("sibling_decisions") or [])[:3]:
        sibling_evidence = sibling.get("evidence") or []
        if not sibling_evidence:
            continue
        sibling_content = sibling.get("content", "")[:60]
        sibling_status = sibling.get("status", "unknown")
        sibling_evidence_lines.append(f"- [{sibling_status}] {sibling_content}...")
        sibling_evidence_lines.extend(
            f"  - {_format_span_ref(span)}" for span in sibling_evidence[:2]
        )
    if sibling_evidence_lines:
        evidence_parts.append("\n[관련 결정사항 근거]")
        evidence_parts.extend(sibling_evidence_lines)

    evidence_section = (
        "\n".join(evidence_parts)
        if evidence_parts
        else "[근거]\n제공된 근거 없음"
    )

    try:
        llm = get_decision_generator_llm()
        chain = DECISION_GENERATION_PROMPT | llm

        result = await chain.ainvoke({
            "meeting_section": meeting_section if meeting_section else "[회의 정보]\n정보 없음",
            "agenda_topic": agenda_topic,
            "decision_content": decision_content,
            "decision_context": decision_context if decision_context else "맥락 정보 없음",
            "evidence_section": evidence_section,
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
