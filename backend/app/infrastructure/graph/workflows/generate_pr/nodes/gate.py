"""generate_pr Hard Gate 노드.

최소 근거 검증:
- agenda/decision에 evidence가 존재해야 함
- evidence의 utterance id가 입력 발화 목록에 존재해야 함
"""

import logging
import re

from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState

logger = logging.getLogger(__name__)

MAX_EVIDENCE_SPAN_TURNS = 10
TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
SUBJECT_PATTERN = re.compile(r"(?:^|\s)[^\s]{1,20}(?:은|는|이|가)(?:\s|$)")
DECISION_OBJECT_PATTERN = re.compile(
    r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9\s()_/-]{0,80}(?:을|를)(?:\s|$)"
)
DECISION_RELAXED_FORM_PATTERN = re.compile(
    r"(?:로|으로|에|까지)\s*(?:확정|결정|채택|유지|중단|연기|보류|적용|도입|선정|제외|추가|삭제|통합|분리|변경|개선|조정)"
)
KOREAN_STOPWORDS = frozenset(
    [
        "그리고",
        "하지만",
        "또한",
        "이번",
        "회의",
        "논의",
        "진행",
        "관련",
        "사항",
        "기반",
        "내용",
        "부분",
        "것",
        "수",
        "등",
    ]
)
ACTION_ITEM_HINTS = (
    "todo",
    "담당",
    "준비",
    "작성",
    "조사",
    "공유",
    "다음 회의",
    "후속",
)
DECISION_VERB_HINTS = (
    "확정",
    "결정",
    "채택",
    "유지",
    "중단",
    "연기",
    "보류",
    "적용",
    "도입",
    "선정",
    "제외",
    "추가",
    "삭제",
    "통합",
    "분리",
    "변경",
    "개선",
)


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in KOREAN_STOPWORDS
    }


def _has_required_object(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return bool(DECISION_OBJECT_PATTERN.search(normalized))


def _has_relaxed_decision_form(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return bool(DECISION_RELAXED_FORM_PATTERN.search(normalized))


def _has_subject(text: str) -> bool:
    return bool(SUBJECT_PATTERN.search(_normalize_text(text)))


def _looks_like_action_item(text: str) -> bool:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return True
    if any(hint in normalized for hint in ACTION_ITEM_HINTS):
        return not any(verb in normalized for verb in DECISION_VERB_HINTS)
    return False


def _build_utterance_maps(
    utterances: list[dict],
) -> tuple[dict[str, str], dict[str, int], list[str], dict[str, str]]:
    alias_to_canonical: dict[str, str] = {}
    order_by_id: dict[str, int] = {}
    ordered_ids: list[str] = []
    text_by_id: dict[str, str] = {}

    for idx, item in enumerate(utterances, start=1):
        raw_id = _normalize_text(item.get("id"))
        canonical_id = raw_id or f"utt-{idx}"
        if canonical_id in order_by_id:
            continue

        order = len(ordered_ids) + 1
        order_by_id[canonical_id] = order
        ordered_ids.append(canonical_id)
        text_by_id[canonical_id] = _normalize_text(item.get("text"))

        alias_to_canonical[canonical_id] = canonical_id
        alias_to_canonical[canonical_id.lower()] = canonical_id
        alias_to_canonical[f"utt-{idx}"] = canonical_id
        alias_to_canonical[str(idx)] = canonical_id

    return alias_to_canonical, order_by_id, ordered_ids, text_by_id


def _expand_utt_alias_candidates(raw_utt_id: str) -> list[str]:
    normalized = _normalize_text(raw_utt_id)
    if not normalized:
        return []

    candidates: list[str] = [normalized]
    compact = normalized.strip("[]()")
    if compact and compact not in candidates:
        candidates.append(compact)

    lowered = compact.lower()
    if lowered.startswith("utt "):
        maybe_id = compact[4:].strip()
        if maybe_id:
            candidates.append(maybe_id)
    if lowered.startswith("utt-"):
        maybe_turn = compact[4:].strip()
        if maybe_turn:
            candidates.append(maybe_turn)
    if lowered.startswith("turn "):
        maybe_turn = compact[5:].strip()
        if maybe_turn:
            candidates.append(maybe_turn)
    if lowered.startswith("turn-"):
        maybe_turn = compact[5:].strip()
        if maybe_turn:
            candidates.append(maybe_turn)
    if compact.isdigit():
        candidates.append(compact)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        for variant in (candidate, candidate.lower()):
            if variant and variant not in seen:
                seen.add(variant)
                deduped.append(variant)

    return deduped


def _canonicalize_utt_id(utt_id: object, alias_to_canonical: dict[str, str]) -> str | None:
    for candidate in _expand_utt_alias_candidates(str(utt_id or "")):
        mapped = alias_to_canonical.get(candidate)
        if mapped:
            return mapped
    return None


def _normalize_span(
    span: dict,
    alias_to_canonical: dict[str, str],
    order_by_id: dict[str, int],
) -> dict | None:
    start = _canonicalize_utt_id(span.get("start_utt_id"), alias_to_canonical)
    end = _canonicalize_utt_id(span.get("end_utt_id"), alias_to_canonical)
    if not start or not end:
        return None

    start_order = order_by_id.get(start)
    end_order = order_by_id.get(end)
    if not start_order or not end_order:
        return None

    if start_order > end_order:
        start, end = end, start
        start_order, end_order = end_order, start_order

    if end_order - start_order + 1 > MAX_EVIDENCE_SPAN_TURNS:
        return None

    normalized_span = dict(span)
    normalized_span["start_utt_id"] = start
    normalized_span["end_utt_id"] = end
    return normalized_span


def _filter_valid_evidence(
    evidence: list[dict],
    alias_to_canonical: dict[str, str],
    order_by_id: dict[str, int],
) -> list[dict]:
    filtered: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for span in evidence:
        if not isinstance(span, dict):
            continue
        normalized_span = _normalize_span(span, alias_to_canonical, order_by_id)
        if normalized_span is None:
            continue
        key = (
            _normalize_text(normalized_span.get("start_utt_id")),
            _normalize_text(normalized_span.get("end_utt_id")),
        )
        if key in seen:
            continue
        seen.add(key)
        filtered.append(normalized_span)

    return filtered


def _collect_evidence_text(
    evidence: list[dict],
    order_by_id: dict[str, int],
    ordered_ids: list[str],
    text_by_id: dict[str, str],
) -> str:
    segments: list[str] = []

    for span in evidence:
        start_id = _normalize_text(span.get("start_utt_id"))
        end_id = _normalize_text(span.get("end_utt_id"))
        start_order = order_by_id.get(start_id)
        end_order = order_by_id.get(end_id)
        if not start_order or not end_order:
            continue

        for canonical_id in ordered_ids[start_order - 1 : end_order]:
            text = text_by_id.get(canonical_id, "")
            if text:
                segments.append(text)

    return " ".join(segments)


def _is_claim_grounded(
    claim: str,
    evidence: list[dict],
    order_by_id: dict[str, int],
    ordered_ids: list[str],
    text_by_id: dict[str, str],
    min_overlap_tokens: int = 1,
    min_coverage: float = 0.25,
) -> bool:
    claim_tokens = _tokenize(_normalize_text(claim))
    if not claim_tokens:
        return False

    evidence_text = _collect_evidence_text(evidence, order_by_id, ordered_ids, text_by_id)
    evidence_tokens = _tokenize(evidence_text)
    if not evidence_tokens:
        return False

    overlap = claim_tokens & evidence_tokens
    if not overlap:
        return False

    required_overlap = min(min_overlap_tokens, len(claim_tokens))
    if len(overlap) < required_overlap:
        return False

    coverage = len(overlap) / max(1, len(claim_tokens))
    return coverage >= min_coverage


async def validate_hard_gate(state: GeneratePrState) -> GeneratePrState:
    """근거 존재/유효성 검증 후 통과 agenda만 저장 단계로 전달."""
    utterances = state.get("generate_pr_transcript_utterances", [])
    agendas = state.get("generate_pr_agendas", [])

    if not agendas:
        return GeneratePrState(generate_pr_agendas=[])

    if not utterances:
        logger.warning("Hard Gate skipped: no utterances found")
        return GeneratePrState(generate_pr_agendas=agendas)

    alias_to_canonical, order_by_id, ordered_ids, text_by_id = _build_utterance_maps(
        list(utterances)
    )
    if not order_by_id:
        logger.warning("Hard Gate skipped: utterance ids not found")
        return GeneratePrState(generate_pr_agendas=agendas)

    passed_agendas: list[dict] = []
    dropped_for_evidence = 0
    dropped_for_grounding = 0
    dropped_decisions_for_form = 0
    dropped_decisions_for_grounding = 0
    normalized_descriptions = 0
    normalized_contexts = 0

    for agenda in agendas:
        if not isinstance(agenda, dict):
            continue

        topic = _normalize_text(agenda.get("topic"))
        description = _normalize_text(agenda.get("description"))
        if not topic:
            dropped_for_grounding += 1
            continue

        agenda_evidence = _filter_valid_evidence(
            list(agenda.get("evidence", []) or []),
            alias_to_canonical,
            order_by_id,
        )
        if not agenda_evidence:
            dropped_for_evidence += 1
            continue

        if not _is_claim_grounded(
            topic,
            agenda_evidence,
            order_by_id,
            ordered_ids,
            text_by_id,
            min_overlap_tokens=1,
            min_coverage=0.2,
        ):
            dropped_for_grounding += 1
            continue

        if description and not _is_claim_grounded(
            description,
            agenda_evidence,
            order_by_id,
            ordered_ids,
            text_by_id,
            min_overlap_tokens=1,
            min_coverage=0.2,
        ):
            description = ""
            normalized_descriptions += 1

        decision = agenda.get("decision")
        if isinstance(decision, dict):
            content = _normalize_text(decision.get("content"))
            context = _normalize_text(decision.get("context"))

            decision = None
            if content:
                decision_evidence = _filter_valid_evidence(
                    list((agenda.get("decision") or {}).get("evidence", []) or []),
                    alias_to_canonical,
                    order_by_id,
                )
                if not decision_evidence:
                    decision_evidence = list(agenda_evidence)

                if not decision_evidence:
                    dropped_decisions_for_grounding += 1
                elif _looks_like_action_item(content):
                    dropped_decisions_for_form += 1
                elif not _has_required_object(content) and not _has_relaxed_decision_form(content):
                    dropped_decisions_for_form += 1
                elif not _is_claim_grounded(
                    content,
                    decision_evidence,
                    order_by_id,
                    ordered_ids,
                    text_by_id,
                    min_overlap_tokens=1,
                    min_coverage=0.18,
                ):
                    dropped_decisions_for_grounding += 1
                else:
                    if context and not _is_claim_grounded(
                        context,
                        decision_evidence,
                        order_by_id,
                        ordered_ids,
                        text_by_id,
                        min_overlap_tokens=1,
                        min_coverage=0.2,
                    ):
                        context = ""
                        normalized_contexts += 1
                    decision = {
                        "content": content,
                        "context": context,
                        "evidence": decision_evidence,
                    }
                    if not _has_subject(content):
                        logger.debug("Decision without explicit subject: %s", content)
        else:
            decision = None

        passed_agendas.append(
            {
                "topic": topic,
                "description": description,
                "evidence": agenda_evidence,
                "decision": decision,
            }
        )

    logger.info(
        "Hard Gate finished: input=%d, passed=%d, drop_evidence=%d, drop_grounding=%d, "
        "drop_decision_form=%d, drop_decision_grounding=%d, normalized_descriptions=%d, normalized_contexts=%d",
        len(agendas),
        len(passed_agendas),
        dropped_for_evidence,
        dropped_for_grounding,
        dropped_decisions_for_form,
        dropped_decisions_for_grounding,
        normalized_descriptions,
        normalized_contexts,
    )

    return GeneratePrState(generate_pr_agendas=passed_agendas)
