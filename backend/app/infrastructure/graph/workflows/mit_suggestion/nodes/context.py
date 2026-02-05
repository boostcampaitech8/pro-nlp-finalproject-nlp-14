"""컨텍스트 수집 노드"""

import logging
from typing import Any

from app.core.neo4j import get_neo4j_driver
from app.models.kg.minutes import KGSpanRef
from app.repositories.kg.repository import KGRepository
from app.infrastructure.graph.workflows.mit_suggestion.state import MitSuggestionState

logger = logging.getLogger(__name__)

# SpanRef 텍스트 추출 시 앞뒤로 추가할 발화 개수
CONTEXT_PADDING = 5


def _normalize_span_refs(raw_refs: Any, *, limit: int) -> list[dict]:
    """SpanRef 리스트를 검증/정규화한다."""
    if not isinstance(raw_refs, list):
        return []

    normalized: list[dict] = []
    for raw in raw_refs:
        if not isinstance(raw, dict):
            continue
        try:
            span = KGSpanRef(**raw)
            if hasattr(span, "model_dump"):
                normalized.append(span.model_dump(exclude_none=True))
            else:
                normalized.append(span.dict(exclude_none=True))
        except Exception as e:
            logger.debug(f"[_normalize_span_refs] Skip invalid span: {e}")
            continue

        if len(normalized) >= limit:
            break

    return normalized


def _ms_to_time(ms: int) -> str:
    """밀리초를 분:초 포맷으로 변환"""
    seconds = ms // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def _extract_evidence_text(
    span_refs: list[dict],
    utterances: list[dict],
    context_padding: int = CONTEXT_PADDING,
) -> list[dict]:
    """SpanRef 범위의 발화 텍스트 + 앞뒤 컨텍스트 추출

    Args:
        span_refs: SpanRef 리스트 [{start_ms, end_ms, ...}]
        utterances: 발화 리스트 [{speaker_name, text, start_ms, end_ms}]
        context_padding: 앞뒤로 추가할 발화 개수

    Returns:
        [
            {
                "time_range": "2:30~3:20",
                "topic_name": "예산 논의",
                "before_context": [{"speaker": "...", "text": "..."}],
                "evidence_utterances": [{"speaker": "...", "text": "..."}],
                "after_context": [{"speaker": "...", "text": "..."}],
            },
            ...
        ]
    """
    if not span_refs or not utterances:
        return []

    # utterances를 start_ms 기준으로 정렬
    sorted_utterances = sorted(utterances, key=lambda u: u.get("start_ms", 0))

    evidence_texts: list[dict] = []

    for span in span_refs:
        span_start_ms = span.get("start_ms")
        span_end_ms = span.get("end_ms")

        if span_start_ms is None or span_end_ms is None:
            continue

        # SpanRef 범위에 해당하는 발화 인덱스 찾기
        evidence_indices: list[int] = []
        for i, utt in enumerate(sorted_utterances):
            utt_start = utt.get("start_ms", 0)
            utt_end = utt.get("end_ms", 0)

            # 발화가 SpanRef 범위와 겹치는지 확인
            if utt_end >= span_start_ms and utt_start <= span_end_ms:
                evidence_indices.append(i)

        if not evidence_indices:
            continue

        # 앞뒤 컨텍스트 인덱스 계산
        first_idx = evidence_indices[0]
        last_idx = evidence_indices[-1]

        before_start = max(0, first_idx - context_padding)
        after_end = min(len(sorted_utterances), last_idx + context_padding + 1)

        # 발화 추출
        before_context = [
            {"speaker": u.get("speaker_name", "Unknown"), "text": u.get("text", "")}
            for u in sorted_utterances[before_start:first_idx]
        ]
        evidence_utterances = [
            {"speaker": u.get("speaker_name", "Unknown"), "text": u.get("text", "")}
            for u in sorted_utterances[first_idx:last_idx + 1]
        ]
        after_context = [
            {"speaker": u.get("speaker_name", "Unknown"), "text": u.get("text", "")}
            for u in sorted_utterances[last_idx + 1:after_end]
        ]

        evidence_texts.append({
            "time_range": f"{_ms_to_time(span_start_ms)}~{_ms_to_time(span_end_ms)}",
            "topic_name": span.get("topic_name"),
            "before_context": before_context,
            "evidence_utterances": evidence_utterances,
            "after_context": after_context,
        })

    return evidence_texts


async def gather_context(state: MitSuggestionState) -> dict:
    """Suggestion 처리를 위한 컨텍스트 수집

    Contract:
        reads: mit_suggestion_decision_id, mit_suggestion_meeting_id, mit_suggestion_utterances
        writes: mit_suggestion_gathered_context
        side-effects: Neo4j 읽기 쿼리
        failures: DB 오류 시 빈 컨텍스트 반환 (graceful degradation)

    수집 내용:
    1. meeting_context: 회의 제목, 날짜, agenda 주제들
    2. thread_history: 원본 Decision에 대한 Comment/Reply 이력 (논의 배경)
    3. sibling_decisions: 같은 Agenda의 다른 Decision들
    4. span_refs: 원본 Decision/Agenda/관련 Decision의 근거 SpanRef
    5. evidence_texts: SpanRef 범위의 실제 발화 텍스트 + 앞뒤 컨텍스트
    """
    decision_id = state.get("mit_suggestion_decision_id")
    meeting_id = state.get("mit_suggestion_meeting_id")
    decision_content = state.get("mit_suggestion_decision_content", "")
    utterances = state.get("mit_suggestion_utterances") or []

    gathered = {
        "decision_summary": decision_content[:500] if decision_content else "",
        "agenda_topic": state.get("mit_suggestion_agenda_topic"),
        "meeting_context": None,
        "thread_history": [],
        "decision_evidence": [],
        "agenda_evidence": [],
        "sibling_decisions": [],
        "decision_evidence_texts": [],  # SpanRef 실제 텍스트
        "agenda_evidence_texts": [],
    }

    if not decision_id:
        logger.warning("[gather_context] No decision_id provided")
        return {"mit_suggestion_gathered_context": gathered}

    try:
        driver = get_neo4j_driver()
        kg_repo = KGRepository(driver)

        # 1. 회의 컨텍스트 조회
        if meeting_id:
            try:
                meeting_context = await kg_repo.get_meeting_context(meeting_id)
                if meeting_context:
                    gathered["meeting_context"] = meeting_context
                    logger.info(f"[gather_context] Meeting context gathered: {meeting_id}")
            except Exception as e:
                logger.warning(f"[gather_context] Failed to get meeting context: {e}")

        # 2. 원본 Decision에 대한 논의 이력 조회
        try:
            thread_history = await kg_repo.get_decision_thread_history(decision_id)
            if thread_history:
                # 최근 10개만, 각 코멘트는 200자로 제한
                gathered["thread_history"] = [
                    {
                        "role": h.get("role", "user"),
                        "content": h.get("content", "")[:200],
                        "author": h.get("author_name", "Unknown"),
                    }
                    for h in thread_history[-10:]
                ]
                logger.info(f"[gather_context] Thread history gathered: {len(gathered['thread_history'])} items")
        except Exception as e:
            logger.warning(f"[gather_context] Failed to get thread history: {e}")

        # 3. 같은 Agenda의 다른 Decision들 + SpanRef 근거 조회
        if meeting_id:
            try:
                minutes_view = await kg_repo.get_minutes_view(meeting_id)
                if minutes_view and minutes_view.get("agendas"):
                    current_agenda = None
                    current_agenda_topic = state.get("mit_suggestion_agenda_topic", "")

                    # 3-1. decision_id로 우선 탐색 (토픽 중복 대비)
                    for agenda in minutes_view.get("agendas", []):
                        if any(
                            d.get("id") == decision_id for d in agenda.get("decisions", [])
                        ):
                            current_agenda = agenda
                            break

                    # 3-2. 토픽으로 fallback 탐색
                    if current_agenda is None and current_agenda_topic:
                        for agenda in minutes_view.get("agendas", []):
                            if agenda.get("topic") == current_agenda_topic:
                                current_agenda = agenda
                                break

                    if current_agenda:
                        gathered["agenda_topic"] = (
                            current_agenda.get("topic") or gathered.get("agenda_topic")
                        )
                        gathered["agenda_evidence"] = _normalize_span_refs(
                            current_agenda.get("evidence"),
                            limit=5,
                        )

                        sibling_decisions: list[dict] = []
                        for d in current_agenda.get("decisions", []):
                            if d.get("id") == decision_id:
                                gathered["decision_evidence"] = _normalize_span_refs(
                                    d.get("evidence"),
                                    limit=8,
                                )
                                continue

                            sibling_decisions.append({
                                "id": d.get("id"),
                                "content": d.get("content", "")[:200],
                                "status": d.get("status"),
                                "evidence": _normalize_span_refs(
                                    d.get("evidence"),
                                    limit=3,
                                ),
                            })
                            if len(sibling_decisions) >= 5:
                                break

                        gathered["sibling_decisions"] = sibling_decisions
                        logger.info(
                            "[gather_context] Evidence gathered: decision=%d agenda=%d sibling_decisions=%d",
                            len(gathered["decision_evidence"]),
                            len(gathered["agenda_evidence"]),
                            len(sibling_decisions),
                        )

                        # 4. SpanRef에서 실제 발화 텍스트 추출 (utterances가 있는 경우)
                        if utterances:
                            gathered["decision_evidence_texts"] = _extract_evidence_text(
                                gathered["decision_evidence"],
                                utterances,
                            )
                            gathered["agenda_evidence_texts"] = _extract_evidence_text(
                                gathered["agenda_evidence"],
                                utterances,
                            )
                            logger.info(
                                "[gather_context] Evidence texts extracted: decision=%d agenda=%d",
                                len(gathered["decision_evidence_texts"]),
                                len(gathered["agenda_evidence_texts"]),
                            )
                    else:
                        logger.info(
                            "[gather_context] Could not find agenda for decision: decision_id=%s",
                            decision_id,
                        )
            except Exception as e:
                logger.warning(f"[gather_context] Failed to get sibling decisions: {e}")

        logger.info(
            f"[gather_context] Context gathered: meeting={bool(gathered['meeting_context'])}, "
            f"threads={len(gathered['thread_history'])}, siblings={len(gathered['sibling_decisions'])}"
        )

    except Exception as e:
        logger.exception(f"[gather_context] Failed to gather context: {e}")

    return {"mit_suggestion_gathered_context": gathered}
