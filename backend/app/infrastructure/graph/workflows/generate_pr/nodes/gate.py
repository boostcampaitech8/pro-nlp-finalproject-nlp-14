"""generate_pr Hard Gate — 의미 기반 근거 검증."""

import logging
import re

import numpy as np

from app.infrastructure.context.embedding import TopicEmbedder
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState

logger = logging.getLogger(__name__)

TOPIC_THRESHOLD = 0.40
DESCRIPTION_THRESHOLD = 0.40
DECISION_THRESHOLD = 0.36
CONTEXT_THRESHOLD = 0.40

DECISION_LEXICAL_OVERLAP_THRESHOLD = 0.10
DECISION_TOPIC_SUPPORT_THRESHOLD = 0.10
DECISION_MIN_LEXICAL_OVERLAP = 0.04

DECISION_CUE_KEYWORDS = (
    "하기로",
    "확정",
    "합의",
    "결정",
    "채택",
    "승인",
    "적용",
    "진행",
)

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]{2,}")


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    return {m.group(0).lower() for m in TOKEN_PATTERN.finditer(_norm(text))}


def _overlap_ratio(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)


def _has_decision_cue(text: str) -> bool:
    lowered = _norm(text).lower()
    return any(cue in lowered for cue in DECISION_CUE_KEYWORDS)


def _decision_supported_by_evidence(
    decision_content: str,
    topic: str,
    evidence: str,
) -> bool:
    """임베딩 유사도가 낮을 때 decision 보존을 위한 lexical fallback."""
    if not decision_content or not evidence:
        return False
    if not _has_decision_cue(decision_content):
        return False

    decision_overlap = _overlap_ratio(
        _tokenize(decision_content),
        _tokenize(evidence),
    )
    topic_overlap = _overlap_ratio(
        _tokenize(topic),
        _tokenize(evidence),
    )
    if decision_overlap >= DECISION_LEXICAL_OVERLAP_THRESHOLD:
        return True
    return (
        decision_overlap >= DECISION_MIN_LEXICAL_OVERLAP
        and topic_overlap >= DECISION_TOPIC_SUPPORT_THRESHOLD
    )


def _build_lookup(
    utterances: list[dict],
) -> tuple[dict[str, str], list[str]]:
    """발화 id → text 매핑 + 순서 리스트. 원본 ID와 utt-N 별칭 모두 등록."""
    id_text: dict[str, str] = {}
    ordered: list[str] = []

    for idx, utt in enumerate(utterances, 1):
        uid = _norm(utt.get("id")) or f"utt-{idx}"
        if uid in id_text:
            continue
        text = _norm(utt.get("text"))
        id_text[uid] = text
        alias = f"utt-{idx}"
        if alias != uid:
            id_text[alias] = text
        ordered.append(uid)

    return id_text, ordered


def _resolve_spans(
    spans: list,
    id_text: dict[str, str],
    ordered: list[str],
) -> str:
    """Evidence spans → 연결 텍스트. 유효하지 않은 span 무시."""
    order = {uid: i for i, uid in enumerate(ordered)}
    for i, uid in enumerate(ordered):
        a = f"utt-{i + 1}"
        if a not in order:
            order[a] = i

    parts: list[str] = []
    for span in spans or []:
        if not isinstance(span, dict):
            continue
        si = order.get(_norm(span.get("start_utt_id")))
        ei = order.get(_norm(span.get("end_utt_id")))
        if si is None or ei is None:
            continue
        if si > ei:
            si, ei = ei, si
        for uid in ordered[si : ei + 1]:
            t = id_text.get(uid, "")
            if t:
                parts.append(t)
    return " ".join(parts)


async def _embed(texts: list[str]) -> dict[str, np.ndarray]:
    """배치 임베딩. API 불가 시 빈 dict."""
    embedder = TopicEmbedder()
    if not embedder.is_available:
        return {}
    unique = list(dict.fromkeys(t for t in texts if t and t.strip()))
    if not unique:
        return {}
    vectors = await embedder.embed_batch_async(unique)
    return {
        t: v
        for t, v in zip(unique, vectors)
        if v is not None and np.linalg.norm(v) > 0
    }


def _grounded(
    claim: str,
    evidence: str,
    vecs: dict[str, np.ndarray],
    threshold: float,
) -> bool:
    """의미 기반 근거 검증. 임베딩 불가 시 통과."""
    if not claim or not evidence:
        return False
    cv, ev = vecs.get(claim), vecs.get(evidence)
    if cv is None or ev is None:
        return True
    return float(TopicEmbedder.cosine_similarity(cv, ev)) >= threshold


async def validate_hard_gate(state: GeneratePrState) -> GeneratePrState:
    """의미 기반 근거 검증 gate."""
    utterances = state.get("generate_pr_transcript_utterances", [])
    agendas = state.get("generate_pr_agendas", [])

    if not agendas:
        return GeneratePrState(generate_pr_agendas=[])
    if not utterances:
        return GeneratePrState(generate_pr_agendas=agendas)

    id_text, ordered = _build_lookup(list(utterances))
    if not id_text:
        return GeneratePrState(generate_pr_agendas=agendas)

    # 임베딩 대상 수집
    to_embed: set[str] = set()
    for ag in agendas:
        if not isinstance(ag, dict):
            continue
        to_embed.update(
            t
            for t in [
                _norm(ag.get("topic")),
                _norm(ag.get("description")),
                _resolve_spans(ag.get("evidence", []), id_text, ordered),
            ]
            if t
        )
        dec = ag.get("decision")
        if isinstance(dec, dict):
            to_embed.update(
                t
                for t in [
                    _norm(dec.get("content")),
                    _norm(dec.get("context")),
                    _resolve_spans(dec.get("evidence", []), id_text, ordered),
                ]
                if t
            )

    vecs = await _embed(list(to_embed))

    # 의미 검증
    passed: list[dict] = []
    lexical_decision_fallback = 0
    for ag in agendas:
        if not isinstance(ag, dict):
            continue
        topic = _norm(ag.get("topic"))
        if not topic:
            continue
        ev = _resolve_spans(ag.get("evidence", []), id_text, ordered)
        if not ev or not _grounded(topic, ev, vecs, TOPIC_THRESHOLD):
            continue

        desc = _norm(ag.get("description"))
        if desc and not _grounded(desc, ev, vecs, DESCRIPTION_THRESHOLD):
            desc = ""

        decision = None
        raw = ag.get("decision")
        if isinstance(raw, dict):
            dc = _norm(raw.get("content"))
            dx = _norm(raw.get("context"))
            de = _resolve_spans(raw.get("evidence", []), id_text, ordered) or ev
            decision_grounded = _grounded(dc, de, vecs, DECISION_THRESHOLD)
            if not decision_grounded and dc:
                decision_grounded = _decision_supported_by_evidence(dc, topic, de)
                if decision_grounded:
                    lexical_decision_fallback += 1
            if dc and decision_grounded:
                if dx and not _grounded(dx, de, vecs, CONTEXT_THRESHOLD):
                    dx = ""
                decision = {
                    "content": dc,
                    "context": dx,
                    "evidence": raw.get("evidence") or list(ag.get("evidence", [])),
                }

        passed.append(
            {
                "topic": topic,
                "description": desc,
                "evidence": ag.get("evidence", []),
                "decision": decision,
            }
        )

    decision_count = sum(1 for item in passed if item.get("decision"))
    logger.info(
        "Hard Gate: in=%d out=%d decisions=%d lexical_fallback=%d semantic=%s",
        len(agendas),
        len(passed),
        decision_count,
        lexical_decision_fallback,
        bool(vecs),
    )
    return GeneratePrState(generate_pr_agendas=passed)
