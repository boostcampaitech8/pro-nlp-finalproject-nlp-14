"""Agenda/Decision 추출 노드 — 2단계 파이프라인.

Step 1 (키워드 추출): 트랜스크립트 → 원자 단위 키워드 + evidence span
Step 2 (회의록 생성): 키워드 + 근거 원문 → 회의록 (topic, description, decision)

모드:
- single pass: 짧은 회의 — Step 1 → Step 2
- chunked pass: 긴 회의 — 청크별 Step 1 → merge → Step 2 1회
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import (
    get_keyword_extractor_llm,
    get_minutes_generator_llm,
)
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState
from app.prompt.v1.workflows.generate_pr import (
    KEYWORD_EXTRACTION_PROMPT,
    MINUTES_GENERATION_PROMPT,
)

logger = logging.getLogger(__name__)

# 청킹 설정 (3청크, 인접 50% overlap)
MAX_CHUNKS = 3
CHUNK_WINDOW_RATIO = 0.5
CHUNK_OVERLAP_RATIO = 0.5
CHUNK_REQUEST_DELAY_SEC = 2.5
CHUNK_MAX_RETRIES = 5
CHUNK_RETRY_DELAY_SEC = 10.0

# 키워드 병합 설정
KEYWORD_MERGE_MIN_OVERLAP = 0.4  # topic_keywords 40% 이상 겹치면 동일 agenda로 판단


# =============================================================================
# Pydantic 스키마 — Step 1 (키워드 추출)
# =============================================================================


class SpanRef(BaseModel):
    """근거 참조 (Utterance 기반)."""

    transcript_id: str = Field(default="meeting-transcript")
    start_utt_id: str = Field(description="근거 시작 발화 ID")
    end_utt_id: str = Field(description="근거 종료 발화 ID")
    sub_start: int | None = Field(default=None, description="발화 내 시작 오프셋")
    sub_end: int | None = Field(default=None, description="발화 내 종료 오프셋")
    start_ms: int | None = Field(default=None, description="근거 시작 시점(ms)")
    end_ms: int | None = Field(default=None, description="근거 종료 시점(ms)")
    topic_id: str | None = Field(default=None, description="근거가 속한 토픽 ID")
    topic_name: str | None = Field(default=None, description="근거가 속한 토픽 이름")


class DecisionKeywords(BaseModel):
    """Step 1: 결정사항 키워드."""

    who: str | None = Field(default=None, description="결정 주체/담당자 (선택)")
    what: str = Field(description="결정 대상/목적어 (필수)")
    when: str | None = Field(default=None, description="기한/시점 (선택)")
    verb: str = Field(description="결정 행위 동사 (필수; 예: 확정, 적용하기로 결정)")
    evidence_spans: list[SpanRef] = Field(
        default_factory=list,
        description="결정 근거 발화 구간",
    )


class AgendaKeywords(BaseModel):
    """Step 1: 아젠다 키워드 그룹."""

    evidence_spans: list[SpanRef] = Field(
        description="아젠다 근거 발화 구간 (필수)",
    )
    topic_keywords: list[str] = Field(
        description="토픽 핵심 키워드 리스트 (명사 + 행위)",
    )
    decision: DecisionKeywords | None = Field(
        default=None,
        description="결정 키워드 (명시적 합의 없으면 null)",
    )


class KeywordExtractionOutput(BaseModel):
    """Step 1 LLM 출력."""

    agendas: list[AgendaKeywords] = Field(
        description="트랜스크립트 등장 순으로 정렬된 아젠다 키워드 그룹",
    )


# =============================================================================
# Pydantic 스키마 — Step 2 (회의록 생성)
# =============================================================================


class MinutesDecisionData(BaseModel):
    """Step 2 LLM 출력: 결정사항 (evidence 없음, 코드에서 Step 1과 결합)."""

    content: str = Field(
        description="[누가] [무엇을] [언제까지] ~하기로 했다 형식의 결정 내용",
    )
    context: str = Field(
        default="",
        description="결정의 근거/맥락 (1문장)",
    )


class MinutesAgendaData(BaseModel):
    """Step 2 LLM 출력: 아젠다 (evidence 없음, 코드에서 Step 1과 결합)."""

    topic: str = Field(description="구체적인 안건명")
    description: str = Field(default="", description="보충 설명 (1문장)")
    decision: MinutesDecisionData | None = Field(
        default=None,
        description="결정사항 (없으면 null)",
    )


class MinutesGenerationOutput(BaseModel):
    """Step 2 LLM 출력."""

    summary: str = Field(description="회의 전체 요약 (3~7문장)")
    agendas: list[MinutesAgendaData] = Field(
        description="키워드 그룹 순서와 동일한 아젠다 목록",
    )


# =============================================================================
# Downstream 전달용 스키마 (gate, persistence 호환)
# =============================================================================


class DecisionData(BaseModel):
    """최종 결정사항 (evidence 포함)."""

    content: str = Field(description="결정 내용")
    context: str = Field(default="", description="결정 맥락/근거")
    evidence: list[SpanRef] = Field(
        default_factory=list,
        description="결정 근거 span 목록",
    )


class AgendaData(BaseModel):
    """최종 아젠다 (evidence 포함)."""

    topic: str = Field(description="안건명")
    description: str = Field(default="", description="보충 설명")
    evidence: list[SpanRef] = Field(
        default_factory=list,
        description="아젠다 근거 span 목록",
    )
    decision: DecisionData | None = Field(default=None, description="결정사항")


class ExtractionOutput(BaseModel):
    """최종 추출 결과 (downstream 호환)."""

    summary: str = Field(description="회의 전체 요약")
    agendas: list[AgendaData] = Field(description="아젠다 목록")


# =============================================================================
# 청킹 데이터 구조
# =============================================================================


@dataclass
class Chunk:
    """청킹된 발화 단위."""
    index: int
    utterances: list[dict]
    topic_ids: list[str] = field(default_factory=list)
    topics_context: str = ""


# =============================================================================
# 헬퍼 함수
# =============================================================================


def _to_int(value: object, fallback: int) -> int:
    """값을 int로 변환, 실패 시 fallback 반환."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return fallback
    return fallback


def _get_topic_turn_range(topic: dict) -> tuple[int, int]:
    """토픽의 (start_turn, end_turn) 반환."""
    start = _to_int(topic.get("startTurn", topic.get("start_turn", topic.get("start_utterance_id"))), 0)
    end = _to_int(topic.get("endTurn", topic.get("end_turn", topic.get("end_utterance_id"))), 0)
    return start, end


def _format_realtime_topics_for_prompt(
    realtime_topics: list[dict],
    max_chars: int = 3000,
) -> str:
    """PR 추출 프롬프트에 주입할 실시간 토픽 컨텍스트 포맷팅."""
    if not realtime_topics:
        return "(없음)"

    sorted_topics = sorted(
        realtime_topics,
        key=lambda item: _get_topic_turn_range(item),
    )

    lines: list[str] = []
    char_count = 0

    for topic in sorted_topics:
        name = str(topic.get("name", "")).strip() or "Untitled"
        summary = str(topic.get("summary", "")).strip() or "(요약 없음)"
        start_turn, end_turn = _get_topic_turn_range(topic)

        keywords_raw = topic.get("keywords", [])
        if isinstance(keywords_raw, list):
            keywords = [str(keyword).strip() for keyword in keywords_raw if str(keyword).strip()]
        else:
            keywords = []
        keywords_text = f" | 키워드: {', '.join(keywords[:5])}" if keywords else ""

        line = (
            f"- [Turn {start_turn}~{end_turn}] {name}: "
            f"{summary[:180]}{keywords_text}"
        )

        if char_count + len(line) + 1 > max_chars:
            break

        lines.append(line)
        char_count += len(line) + 1

    return "\n".join(lines) if lines else "(없음)"


def _prepare_utterances(state: GeneratePrState) -> list[dict]:
    """입력 발화를 정규화한다."""
    utterances = list(state.get("generate_pr_transcript_utterances", []) or [])
    if utterances:
        normalized: list[dict] = []
        for turn, utt in enumerate(utterances, start=1):
            original_id = str(utt.get("id", "")).strip()
            if not original_id:
                original_id = f"utt-{turn}"
            llm_utt_id = f"utt-{turn}"
            normalized.append({
                "id": original_id,
                "llm_utt_id": llm_utt_id,
                "speaker_name": str(utt.get("speaker_name", "") or "Unknown"),
                "text": str(utt.get("text", "") or ""),
                "start_ms": utt.get("start_ms"),
                "end_ms": utt.get("end_ms"),
                "turn": turn,
            })
        return normalized

    transcript = state.get("generate_pr_transcript_text", "")
    if not transcript:
        return []

    return [{
        "id": "utt-1",
        "llm_utt_id": "utt-1",
        "speaker_name": "Unknown",
        "text": transcript,
        "start_ms": None,
        "end_ms": None,
        "turn": 1,
    }]


def _format_utterances_for_prompt(utterances: list[dict]) -> str:
    """발화를 프롬프트용 텍스트로 포맷."""
    lines: list[str] = []
    for utt in utterances:
        llm_utt_id = str(utt.get("llm_utt_id") or utt.get("id") or "")
        lines.append(
            f"[Turn {utt['turn']}] [Utt {llm_utt_id}] "
            f"{utt['speaker_name']}: {utt['text']}"
        )
    return "\n".join(lines)


# =============================================================================
# Utterance ID 해석
# =============================================================================


def _normalize_key(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _build_utt_alias_to_index(utterances: list[dict]) -> dict[str, int]:
    alias_to_index: dict[str, int] = {}

    for idx, utterance in enumerate(utterances):
        original_id = _normalize_key(utterance.get("id"))
        llm_utt_id = _normalize_key(utterance.get("llm_utt_id"))
        turn = int(utterance.get("turn") or (idx + 1))

        aliases = {
            original_id,
            original_id.lower(),
            llm_utt_id,
            llm_utt_id.lower(),
            str(turn),
            f"utt-{turn}",
            f"turn-{turn}",
            f"utt {turn}",
            f"turn {turn}",
        }
        for alias in aliases:
            if alias:
                alias_to_index[alias] = idx

    return alias_to_index


def _expand_utt_alias_candidates(raw_utt_id: str) -> list[str]:
    normalized = _normalize_key(raw_utt_id)
    if not normalized:
        return []

    candidates: list[str] = [normalized]
    compact = normalized.strip("[]()")
    if compact and compact not in candidates:
        candidates.append(compact)

    lowered = compact.lower()
    if lowered.startswith("utt "):
        turn = compact[4:].strip()
        if turn:
            candidates.append(turn)
    if lowered.startswith("utt-"):
        turn = compact[4:].strip()
        if turn:
            candidates.append(turn)
    if lowered.startswith("turn "):
        turn = compact[5:].strip()
        if turn:
            candidates.append(turn)
    if lowered.startswith("turn-"):
        turn = compact[5:].strip()
        if turn:
            candidates.append(turn)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        for variant in (candidate, candidate.lower()):
            if variant and variant not in seen:
                seen.add(variant)
                deduped.append(variant)

    return deduped


def _resolve_utt_index(raw_utt_id: object, alias_to_index: dict[str, int]) -> int | None:
    for candidate in _expand_utt_alias_candidates(str(raw_utt_id or "")):
        mapped = alias_to_index.get(candidate)
        if mapped is not None:
            return mapped
    return None


# =============================================================================
# Evidence 정규화
# =============================================================================


def _canonicalize_evidence(
    evidence: list[dict],
    utterances: list[dict],
    alias_to_index: dict[str, int],
    topic_id: str | None = None,
    topic_name: str | None = None,
) -> list[dict]:
    """LLM이 출력한 evidence span을 정규화한다."""
    canonical: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for span in evidence:
        if not isinstance(span, dict):
            continue

        start_idx = _resolve_utt_index(span.get("start_utt_id"), alias_to_index)
        end_idx = _resolve_utt_index(span.get("end_utt_id"), alias_to_index)
        if start_idx is None or end_idx is None:
            continue

        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        start_utt = utterances[start_idx]
        end_utt = utterances[end_idx]
        start_id = str(start_utt.get("id", "")).strip()
        end_id = str(end_utt.get("id", "")).strip()
        if not start_id or not end_id:
            continue

        key = (start_id, end_id)
        if key in seen:
            continue
        seen.add(key)

        normalized_span = dict(span)
        normalized_span["start_utt_id"] = start_id
        normalized_span["end_utt_id"] = end_id
        normalized_span["start_ms"] = start_utt.get("start_ms")
        normalized_span["end_ms"] = end_utt.get("end_ms")
        if not normalized_span.get("topic_id") and topic_id:
            normalized_span["topic_id"] = topic_id
        if not normalized_span.get("topic_name") and topic_name:
            normalized_span["topic_name"] = topic_name
        canonical.append(normalized_span)

    return canonical


def _resolve_evidence_text(
    evidence: list[dict],
    utterances: list[dict],
    alias_to_index: dict[str, int],
    max_chars: int = 500,
) -> str:
    """evidence span에 해당하는 발화 원문을 추출한다."""
    segments: list[str] = []

    for span in evidence:
        start_idx = _resolve_utt_index(span.get("start_utt_id"), alias_to_index)
        end_idx = _resolve_utt_index(span.get("end_utt_id"), alias_to_index)
        if start_idx is None or end_idx is None:
            continue
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        for utt in utterances[start_idx : end_idx + 1]:
            text = str(utt.get("text", "")).strip()
            speaker = str(utt.get("speaker_name", "")).strip()
            if text:
                segments.append(f"{speaker}: {text}" if speaker else text)

    result = " ".join(segments)
    return result[:max_chars] if len(result) > max_chars else result


# =============================================================================
# 3청크 슬라이딩 청킹
# =============================================================================


def _select_topics_for_window(
    realtime_topics: list[dict],
    start_turn: int,
    end_turn: int,
) -> list[dict]:
    """청크 turn 범위와 겹치는 토픽만 선택."""
    relevant: list[dict] = []
    for topic in realtime_topics:
        topic_start, topic_end = _get_topic_turn_range(topic)
        if topic_start <= end_turn and topic_end >= start_turn:
            relevant.append(topic)
    return relevant


def _build_three_chunk_starts(total_utterances: int) -> tuple[int, list[int]]:
    """3청크(50% overlap)용 window/start 계산."""
    if total_utterances <= 0:
        return 0, []

    window_size = max(1, math.ceil(total_utterances * CHUNK_WINDOW_RATIO))
    stride = max(1, int(window_size * (1 - CHUNK_OVERLAP_RATIO)))

    max_start = max(0, total_utterances - window_size)
    raw_starts = [0, stride, stride * 2]
    starts: list[int] = []
    for raw_start in raw_starts[:MAX_CHUNKS]:
        start = min(raw_start, max_start)
        if not starts or starts[-1] != start:
            starts.append(start)

    return window_size, starts


def _create_three_overlap_chunks(
    utterances: list[dict],
    realtime_topics: list[dict],
) -> list[Chunk]:
    """고정 3청크 생성 (청크 크기=전체의 50%, 인접 청크 50% overlap)."""
    chunks: list[Chunk] = []
    if not utterances:
        return chunks

    window_size, starts = _build_three_chunk_starts(len(utterances))
    if not starts:
        return chunks

    for start in starts:
        window_utts = utterances[start:start + window_size]
        if not window_utts:
            continue

        start_turn = int(window_utts[0]["turn"])
        end_turn = int(window_utts[-1]["turn"])
        relevant_topics = _select_topics_for_window(realtime_topics, start_turn, end_turn)

        topic_ids = [
            str(topic.get("id", "")).strip()
            for topic in relevant_topics
            if str(topic.get("id", "")).strip()
        ]

        chunks.append(Chunk(
            index=len(chunks),
            utterances=window_utts,
            topic_ids=topic_ids,
            topics_context=_format_realtime_topics_for_prompt(relevant_topics),
        ))

    return chunks


# =============================================================================
# 키워드 병합 (chunked pass용)
# =============================================================================


def _keywords_overlap_ratio(kws_a: list[str], kws_b: list[str]) -> float:
    """두 keyword 리스트의 겹침 비율 (Jaccard-like)."""
    set_a = {kw.lower().strip() for kw in kws_a if kw.strip()}
    set_b = {kw.lower().strip() for kw in kws_b if kw.strip()}
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _merge_evidence_spans(spans_a: list[dict], spans_b: list[dict]) -> list[dict]:
    """두 evidence span 리스트를 중복 제거하여 병합."""
    merged: list[dict] = list(spans_a)
    seen = {
        (_normalize_key(s.get("start_utt_id")), _normalize_key(s.get("end_utt_id")))
        for s in spans_a
    }
    for span in spans_b:
        key = (_normalize_key(span.get("start_utt_id")), _normalize_key(span.get("end_utt_id")))
        if key not in seen:
            seen.add(key)
            merged.append(span)
    return merged


def _merge_keyword_groups(
    all_chunk_keywords: list[list[dict]],
) -> list[dict]:
    """여러 청크의 키워드 그룹을 유사 agenda끼리 병합한다.

    Args:
        all_chunk_keywords: 청크별 agenda keyword dict 리스트의 리스트

    Returns:
        병합된 agenda keyword dict 리스트
    """
    merged: list[dict] = []

    for chunk_keywords in all_chunk_keywords:
        for kw_group in chunk_keywords:
            topic_kws = list(kw_group.get("topic_keywords", []))

            # 기존 merged에서 유사 agenda 찾기
            best_match_idx = -1
            best_overlap = 0.0
            for idx, existing in enumerate(merged):
                overlap = _keywords_overlap_ratio(
                    topic_kws, existing.get("topic_keywords", [])
                )
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match_idx = idx

            if best_overlap >= KEYWORD_MERGE_MIN_OVERLAP and best_match_idx >= 0:
                # 기존 agenda에 병합
                existing = merged[best_match_idx]
                # topic_keywords 합집합
                existing_kws = set(existing.get("topic_keywords", []))
                for kw in topic_kws:
                    if kw not in existing_kws:
                        existing["topic_keywords"].append(kw)
                        existing_kws.add(kw)
                # evidence_spans 병합
                existing["evidence_spans"] = _merge_evidence_spans(
                    existing.get("evidence_spans", []),
                    kw_group.get("evidence_spans", []),
                )
                # decision 병합 (없던 것이 새로 나오면 추가)
                if kw_group.get("decision") and not existing.get("decision"):
                    existing["decision"] = kw_group["decision"]
                elif kw_group.get("decision") and existing.get("decision"):
                    # decision evidence 병합
                    existing["decision"]["evidence_spans"] = _merge_evidence_spans(
                        existing["decision"].get("evidence_spans", []),
                        kw_group["decision"].get("evidence_spans", []),
                    )
            else:
                # 새 agenda로 추가
                merged.append(dict(kw_group))

    return merged


# =============================================================================
# Step 2 입력 포맷팅
# =============================================================================


def _format_keywords_for_minutes_prompt(
    keyword_groups: list[dict],
    utterances: list[dict],
    alias_to_index: dict[str, int],
) -> str:
    """키워드 그룹 + 근거 원문을 Step 2 프롬프트용 텍스트로 포맷한다."""
    sections: list[str] = []

    for idx, group in enumerate(keyword_groups):
        lines: list[str] = [f"### 아젠다 {idx + 1}"]

        # topic keywords
        topic_kws = group.get("topic_keywords", [])
        lines.append(f"키워드: {', '.join(topic_kws)}")

        # agenda evidence text
        agenda_evidence = group.get("evidence_spans", [])
        evidence_text = _resolve_evidence_text(
            agenda_evidence, utterances, alias_to_index, max_chars=800
        )
        if evidence_text:
            lines.append(f"근거 원문: {evidence_text}")

        # decision keywords
        decision = group.get("decision")
        if decision:
            decision_parts: list[str] = []
            if decision.get("who"):
                decision_parts.append(f"누가: {decision['who']}")
            decision_parts.append(f"무엇을: {decision.get('what', '')}")
            if decision.get("when"):
                decision_parts.append(f"언제까지: {decision['when']}")
            decision_parts.append(f"행위: {decision.get('verb', '')}")
            lines.append(f"결정 키워드: {' | '.join(decision_parts)}")

            # decision evidence text
            dec_evidence = decision.get("evidence_spans", [])
            dec_evidence_text = _resolve_evidence_text(
                dec_evidence, utterances, alias_to_index, max_chars=400
            )
            if dec_evidence_text:
                lines.append(f"결정 근거 원문: {dec_evidence_text}")
        else:
            lines.append("결정: 없음")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# =============================================================================
# Step 1 + Step 2 결합
# =============================================================================


def _combine_minutes_with_evidence(
    minutes: MinutesGenerationOutput,
    keyword_groups: list[dict],
    utterances: list[dict],
    alias_to_index: dict[str, int],
    topic_id: str | None = None,
    topic_name: str | None = None,
) -> list[dict]:
    """Step 2 LLM 출력과 Step 1 evidence를 결합하여 최종 agenda dict를 생성한다."""
    agendas: list[dict] = []

    for idx, minutes_agenda in enumerate(minutes.agendas):
        # 대응하는 keyword group (순서 기반 매칭)
        kw_group = keyword_groups[idx] if idx < len(keyword_groups) else {}

        # agenda evidence (Step 1)
        agenda_evidence = _canonicalize_evidence(
            kw_group.get("evidence_spans", []),
            utterances,
            alias_to_index,
            topic_id=topic_id,
            topic_name=topic_name,
        )
        if not agenda_evidence:
            continue

        # decision (Step 2 content + Step 1 evidence)
        decision_data = None
        if minutes_agenda.decision and kw_group.get("decision"):
            decision_evidence = _canonicalize_evidence(
                kw_group["decision"].get("evidence_spans", []),
                utterances,
                alias_to_index,
                topic_id=topic_id,
                topic_name=topic_name,
            )
            if not decision_evidence:
                decision_evidence = list(agenda_evidence)

            decision_data = {
                "content": minutes_agenda.decision.content.strip(),
                "context": minutes_agenda.decision.context.strip(),
                "evidence": decision_evidence,
            }

        agendas.append({
            "topic": minutes_agenda.topic.strip(),
            "description": minutes_agenda.description.strip(),
            "evidence": agenda_evidence,
            "decision": decision_data,
        })

    return agendas


# =============================================================================
# LLM 체인 호출
# =============================================================================


def _invoke_keyword_chain(
    transcript_text: str,
    realtime_topics_text: str,
) -> KeywordExtractionOutput:
    """Step 1: 키워드 추출 LLM 체인."""
    parser = PydanticOutputParser(pydantic_object=KeywordExtractionOutput)
    prompt = ChatPromptTemplate.from_template(KEYWORD_EXTRACTION_PROMPT)
    chain = prompt | get_keyword_extractor_llm() | parser

    return chain.invoke({
        "realtime_topics": realtime_topics_text,
        "transcript": transcript_text,
        "format_instructions": parser.get_format_instructions(),
    })


def _invoke_minutes_chain(
    keyword_groups_text: str,
    realtime_topics_text: str,
) -> MinutesGenerationOutput:
    """Step 2: 회의록 생성 LLM 체인."""
    parser = PydanticOutputParser(pydantic_object=MinutesGenerationOutput)
    prompt = ChatPromptTemplate.from_template(MINUTES_GENERATION_PROMPT)
    chain = prompt | get_minutes_generator_llm() | parser

    return chain.invoke({
        "realtime_topics": realtime_topics_text,
        "keyword_groups": keyword_groups_text,
        "format_instructions": parser.get_format_instructions(),
    })


def _is_rate_limit_error(error: Exception) -> bool:
    """429/Rate limit 계열 에러 여부를 문자열 기반으로 판별."""
    message = str(error).lower()
    return (
        "429" in message
        or "too many requests" in message
        or "rate exceeded" in message
        or "rate limit" in message
    )


async def _invoke_keyword_chain_with_retry(
    transcript_text: str,
    realtime_topics_text: str,
    chunk_index: int,
) -> KeywordExtractionOutput:
    """청크별 Step 1 호출 (rate-limit 완화를 위한 재시도 포함)."""
    last_error: Exception | None = None
    for attempt in range(1, CHUNK_MAX_RETRIES + 1):
        try:
            return _invoke_keyword_chain(transcript_text, realtime_topics_text)
        except Exception as error:
            last_error = error
            if attempt >= CHUNK_MAX_RETRIES:
                break

            backoff = CHUNK_RETRY_DELAY_SEC
            if _is_rate_limit_error(error):
                logger.warning(
                    "Keyword extraction rate-limited: idx=%d attempt=%d/%d backoff=%.1fs",
                    chunk_index,
                    attempt,
                    CHUNK_MAX_RETRIES,
                    backoff,
                )
            else:
                logger.warning(
                    "Keyword extraction retrying: idx=%d attempt=%d/%d backoff=%.1fs error=%s",
                    chunk_index,
                    attempt,
                    CHUNK_MAX_RETRIES,
                    backoff,
                    error,
                )

            await asyncio.sleep(backoff)

    if last_error:
        raise last_error
    raise RuntimeError("Keyword extraction failed without explicit error")


async def _invoke_minutes_chain_with_retry(
    keyword_groups_text: str,
    realtime_topics_text: str,
    *,
    phase: str,
) -> MinutesGenerationOutput:
    """Step 2 호출 재시도 (rate-limit 포함 10초 간격)."""
    last_error: Exception | None = None
    for attempt in range(1, CHUNK_MAX_RETRIES + 1):
        try:
            return _invoke_minutes_chain(keyword_groups_text, realtime_topics_text)
        except Exception as error:
            last_error = error
            if attempt >= CHUNK_MAX_RETRIES:
                break

            backoff = CHUNK_RETRY_DELAY_SEC
            if _is_rate_limit_error(error):
                logger.warning(
                    "Minutes generation rate-limited: phase=%s attempt=%d/%d backoff=%.1fs",
                    phase,
                    attempt,
                    CHUNK_MAX_RETRIES,
                    backoff,
                )
            else:
                logger.warning(
                    "Minutes generation retrying: phase=%s attempt=%d/%d backoff=%.1fs error=%s",
                    phase,
                    attempt,
                    CHUNK_MAX_RETRIES,
                    backoff,
                    error,
                )

            await asyncio.sleep(backoff)

    if last_error:
        raise last_error
    raise RuntimeError("Minutes generation failed without explicit error")


# =============================================================================
# Step 1 결과를 dict로 변환
# =============================================================================


def _keyword_output_to_dicts(output: KeywordExtractionOutput) -> list[dict]:
    """KeywordExtractionOutput을 dict 리스트로 변환."""
    result: list[dict] = []
    for agenda in output.agendas:
        agenda_dict: dict = {
            "evidence_spans": [span.model_dump() for span in agenda.evidence_spans],
            "topic_keywords": list(agenda.topic_keywords),
        }
        if agenda.decision:
            agenda_dict["decision"] = {
                "who": agenda.decision.who,
                "what": agenda.decision.what,
                "when": agenda.decision.when,
                "verb": agenda.decision.verb,
                "evidence_spans": [span.model_dump() for span in agenda.decision.evidence_spans],
            }
        else:
            agenda_dict["decision"] = None
        result.append(agenda_dict)
    return result


# =============================================================================
# 2단계 파이프라인 실행
# =============================================================================


async def _run_two_step_pipeline(
    keyword_groups: list[dict],
    utterances: list[dict],
    realtime_topics_text: str,
    topic_id: str | None = None,
    topic_name: str | None = None,
    *,
    phase: str,
) -> tuple[list[dict], str]:
    """Step 1 결과(keyword_groups)를 받아 Step 2를 실행하고 최종 agenda를 반환한다.

    Returns:
        (agendas, summary)
    """
    if not keyword_groups:
        return [], ""

    alias_to_index = _build_utt_alias_to_index(utterances)

    # 근거 없는 그룹 필터링
    valid_groups = [
        g for g in keyword_groups
        if g.get("evidence_spans") and g.get("topic_keywords")
    ]
    if not valid_groups:
        return [], ""

    # 키워드 병합 (중복 agenda 통합 — Step 2 1:1 매핑을 위해 코드에서 선행 처리)
    valid_groups = _merge_keyword_groups([valid_groups])

    # Step 2 프롬프트 포맷팅
    keyword_groups_text = _format_keywords_for_minutes_prompt(
        valid_groups, utterances, alias_to_index
    )

    # Step 2 LLM 호출
    minutes_output = await _invoke_minutes_chain_with_retry(
        keyword_groups_text,
        realtime_topics_text,
        phase=phase,
    )

    # Step 1 evidence + Step 2 minutes 결합
    agendas = _combine_minutes_with_evidence(
        minutes_output,
        valid_groups,
        utterances,
        alias_to_index,
        topic_id=topic_id,
        topic_name=topic_name,
    )

    return agendas, minutes_output.summary.strip()


# =============================================================================
# 추출 노드
# =============================================================================


async def extract_single(state: GeneratePrState) -> GeneratePrState:
    """짧은 회의 추출: single pass (Step 1 → Step 2)."""
    utterances = _prepare_utterances(state)
    if not utterances:
        logger.warning("트랜스크립트가 비어있습니다")
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")

    transcript_text = _format_utterances_for_prompt(utterances)
    realtime_topics = state.get("generate_pr_realtime_topics", []) or []
    topics_text = _format_realtime_topics_for_prompt(realtime_topics)

    try:
        # Step 1: 키워드 추출
        keyword_output = _invoke_keyword_chain(transcript_text, topics_text)
        keyword_groups = _keyword_output_to_dicts(keyword_output)

        logger.debug(
            "Single pass Step 1 complete: keyword_groups=%d",
            len(keyword_groups),
        )

        # Step 2: 회의록 생성 + evidence 결합
        agendas, summary = await _run_two_step_pipeline(
            keyword_groups,
            utterances,
            topics_text,
            phase="single",
        )

        logger.info(
            "Single pass Step 2 complete: agendas=%d",
            len(agendas),
        )

        return GeneratePrState(
            generate_pr_agendas=agendas,
            generate_pr_summary=summary,
            generate_pr_chunks=[{
                "index": 0,
                "utterance_count": len(utterances),
            }],
        )
    except Exception as e:
        logger.error("Single pass extraction failed: %s", e)
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")


async def extract_chunked(state: GeneratePrState) -> GeneratePrState:
    """긴 회의 추출: 청크별 Step 1 → merge → Step 2 1회."""
    utterances = _prepare_utterances(state)
    if not utterances:
        logger.warning("트랜스크립트가 비어있습니다")
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")

    realtime_topics = list(state.get("generate_pr_realtime_topics", []) or [])
    chunks = _create_three_overlap_chunks(utterances, realtime_topics)

    if len(chunks) <= 1:
        return await extract_single(state)

    logger.debug(
        "Chunked extraction: chunks=%d, topics=%d",
        len(chunks),
        len(realtime_topics),
    )

    # 청크별 Step 1
    all_chunk_keywords: list[list[dict]] = []
    chunk_meta: list[dict] = []

    for chunk_idx, chunk in enumerate(chunks):
        transcript_text = _format_utterances_for_prompt(chunk.utterances)
        topics_text = chunk.topics_context or _format_realtime_topics_for_prompt(
            [t for t in realtime_topics if str(t.get("id", "")) in chunk.topic_ids]
        )

        try:
            keyword_output = await _invoke_keyword_chain_with_retry(
                transcript_text, topics_text, chunk.index
            )
            keyword_groups = _keyword_output_to_dicts(keyword_output)

            logger.debug(
                "Chunk Step 1 complete: idx=%d keyword_groups=%d",
                chunk.index,
                len(keyword_groups),
            )

            all_chunk_keywords.append(keyword_groups)
            chunk_meta.append({
                "index": chunk.index,
                "utterance_count": len(chunk.utterances),
                "topic_ids": chunk.topic_ids,
            })
        except Exception as e:
            logger.warning("Chunk Step 1 failed: idx=%d error=%s", chunk.index, e)

        if chunk_idx < len(chunks) - 1:
            await asyncio.sleep(CHUNK_REQUEST_DELAY_SEC)

    if not all_chunk_keywords:
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")

    # 키워드 병합
    merged_keywords = _merge_keyword_groups(all_chunk_keywords)

    logger.debug(
        "Keyword merge complete: chunks=%d, merged_groups=%d",
        len(all_chunk_keywords),
        len(merged_keywords),
    )

    # Step 2: 병합된 키워드로 회의록 1회 생성
    topics_text = _format_realtime_topics_for_prompt(realtime_topics)

    try:
        agendas, summary = await _run_two_step_pipeline(
            merged_keywords,
            utterances,
            topics_text,
            phase="chunked",
        )

        logger.info(
            "Chunked Step 2 complete: agendas=%d",
            len(agendas),
        )

        return GeneratePrState(
            generate_pr_agendas=agendas,
            generate_pr_summary=summary,
            generate_pr_chunks=chunk_meta,
        )
    except Exception as e:
        logger.error("Chunked Step 2 failed: %s", e)
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")


async def extract_agendas(state: GeneratePrState) -> GeneratePrState:
    """하위 호환용 진입점: 기존 extractor 호출은 single pass로 처리."""
    return await extract_single(state)
