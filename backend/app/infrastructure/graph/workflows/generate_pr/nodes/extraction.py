"""Agenda/Decision 추출 노드.

문서 설계에 맞춰 다음 모드를 지원한다.
- single pass: 짧은 회의는 1회 추출
- chunked pass: 긴 회의는 3청크(50% overlap)로 추출 후 토픽 기반 병합
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import get_pr_generator_llm
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState
from app.prompt.v1.workflows.generate_pr import (
    AGENDA_EXTRACTION_PROMPT,
    AGENDA_MERGE_PROMPT,
    SUMMARY_REFINEMENT_PROMPT,
)

logger = logging.getLogger(__name__)

# 청킹 설정 (3청크, 인접 50% overlap)
MAX_CHUNKS = 3
CHUNK_WINDOW_RATIO = 0.5
CHUNK_OVERLAP_RATIO = 0.5
CHUNK_REQUEST_DELAY_SEC = 2.5
CHUNK_MAX_RETRIES = 5
CHUNK_RATE_LIMIT_BACKOFF_BASE_SEC = 5.0
CHUNK_RATE_LIMIT_BACKOFF_MAX_SEC = 20.0

# Evidence overlap 병합 임계값 (50% 이상 겹치면 병합)
EVIDENCE_OVERLAP_MERGE_THRESHOLD = 0.5

# Topic 키워드 유사도 병합 임계값 (50% 이상 겹치면 병합)
TOPIC_KEYWORD_OVERLAP_THRESHOLD = 0.5

# 한국어 불용어 (토픽 키워드 추출 시 제외)
KOREAN_STOPWORDS = frozenset([
    "및", "의", "에", "를", "을", "이", "가", "은", "는", "로", "으로",
    "에서", "와", "과", "도", "만", "부터", "까지", "에게", "한", "할",
    "하는", "된", "되는", "위한", "대한", "관한", "통한", "관련",
    "기반", "방안", "방식", "내용", "사항", "진행", "검토", "논의",
    "확인", "결정", "도입", "적용", "활용", "개선", "추가", "변경",
])


class SpanRef(BaseModel):
    """근거 참조 (Utterance + Topic 기반)."""

    transcript_id: str = Field(default="meeting-transcript")
    start_utt_id: str = Field(description="근거 시작 발화 ID")
    end_utt_id: str = Field(description="근거 종료 발화 ID")
    sub_start: int | None = Field(default=None, description="발화 내 시작 오프셋")
    sub_end: int | None = Field(default=None, description="발화 내 종료 오프셋")
    start_ms: int | None = Field(default=None, description="근거 시작 시점(ms)")
    end_ms: int | None = Field(default=None, description="근거 종료 시점(ms)")
    # 토픽 힌트 (선택, 병합/검색에 활용)
    topic_id: str | None = Field(default=None, description="근거가 속한 토픽 ID")
    topic_name: str | None = Field(default=None, description="근거가 속한 토픽 이름")


class DecisionData(BaseModel):
    """추출된 결정사항."""

    content: str = Field(
        description=(
            "해당 아젠다에서 최종 합의된 단일 결정 내용. "
            "명시적 확정/합의/보류 결정만 포함하고, 액션 아이템/제안/단순 의견은 제외."
        )
    )
    context: str = Field(
        default="",
        description=(
            "결정의 근거/맥락/제약. "
            "결정이 그렇게 정해진 이유를 서술하며 status/승인 정보는 포함하지 않음."
        ),
    )
    evidence: list[SpanRef] = Field(
        default_factory=list,
        description="결정 근거 span 목록 (없으면 chunk 범위로 fallback)",
    )


class AgendaData(BaseModel):
    """추출된 아젠다."""

    topic: str = Field(
        description=(
            "작고 구체적인 아젠다 주제(한 가지 핵심). "
            "커밋 메시지처럼 논의 단위를 잘게 쪼갠 제목."
        )
    )
    description: str = Field(
        default="",
        description=(
            "아젠다의 핵심 논의 내용 요약(1문장 권장). "
            "트랜스크립트 근거 기반으로 작성."
        ),
    )
    evidence: list[SpanRef] = Field(
        default_factory=list,
        description="아젠다 근거 span 목록 (없으면 chunk 범위로 fallback)",
    )
    decision: DecisionData | None = Field(
        default=None,
        description=(
            "해당 아젠다의 결정사항(Agenda당 최대 1개). "
            "명시적 합의가 없으면 null."
        ),
    )


class ExtractionOutput(BaseModel):
    """LLM 추출 결과."""

    summary: str = Field(
        description=(
            "회의 전체 요약(3-7문장). "
            "핵심 논의 흐름과 결론을 포함."
        )
    )
    agendas: list[AgendaData] = Field(
        description=(
            "트랜스크립트 등장 순으로 정렬된 아젠다 목록. "
            "유사 표현은 병합하고, 근거 없는 항목은 제외."
        )
    )


class AgendaMergeGroup(BaseModel):
    """LLM 병합 결과의 단일 그룹."""

    source_agenda_ids: list[str] = Field(
        default_factory=list,
        description="병합 대상 source agenda id 목록",
    )
    merged_topic: str = Field(default="", description="병합 후 최종 topic")
    merged_description: str = Field(default="", description="병합 후 최종 description")
    merged_decision_content: str | None = Field(
        default=None,
        description="병합 후 최종 decision content (없으면 null)",
    )
    merged_decision_context: str | None = Field(
        default=None,
        description="병합 후 최종 decision context (없으면 null)",
    )


class AgendaMergeOutput(BaseModel):
    """LLM 병합 출력 스키마."""

    merged_agendas: list[AgendaMergeGroup] = Field(default_factory=list)


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
                # upstream ID가 없을 때만 제한적으로 fallback 사용
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


def _build_chunk_span(
    chunk_utterances: list[dict],
    topic_id: str | None = None,
    topic_name: str | None = None,
) -> list[dict]:
    """청크 범위를 SpanRef 형태로 반환."""
    if not chunk_utterances:
        return []
    first = chunk_utterances[0]
    last = chunk_utterances[-1]
    return [{
        "transcript_id": "meeting-transcript",
        "start_utt_id": str(first["id"]),
        "end_utt_id": str(last["id"]),
        "start_ms": first.get("start_ms"),
        "end_ms": last.get("end_ms"),
        "topic_id": topic_id,
        "topic_name": topic_name,
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
# 토픽 기반 병합 (Topic-Guided Merge)
# =============================================================================


def _find_topic_for_evidence(
    evidence: list[dict],
    topics: list[dict],
) -> str | None:
    """Evidence의 발화 ID가 속한 토픽 ID 반환."""
    if not evidence or not topics:
        return None

    # 0) evidence에 topic_id가 있으면 우선 사용 (UUID 기반 utt_id에서도 안정적)
    first_evidence = evidence[0]
    topic_id = first_evidence.get("topic_id")
    if isinstance(topic_id, str) and topic_id.strip():
        return topic_id.strip()

    # 1) 첫 번째 evidence의 발화 ID 기준 fallback
    start_utt_id = first_evidence.get("start_utt_id", "")

    # utt_id에서 turn 번호 추출 시도
    try:
        # "utt-1" 형식이거나 숫자인 경우
        if isinstance(start_utt_id, str) and start_utt_id.startswith("utt-"):
            utt_turn = int(start_utt_id.split("-")[1])
        else:
            utt_turn = int(start_utt_id)
    except (ValueError, IndexError):
        return None

    for topic in topics:
        start_turn, end_turn = _get_topic_turn_range(topic)
        if start_turn <= utt_turn <= end_turn:
            return str(topic.get("id", ""))

    return None


def _merge_chunk_results_with_topics(
    chunk_results: list[dict],
    topics: list[dict],
) -> list[dict]:
    """토픽 정보를 활용한 스마트 병합.

    원칙:
    1. 같은 토픽 내 항목 → 중복 가능성 높음 → 병합 검토
    2. 다른 토픽의 항목 → 기본적으로 분리 유지
    """
    if not topics:
        return _merge_chunk_results_simple(chunk_results)

    # 1. 모든 아젠다를 topic_id로 그룹핑
    by_topic: dict[str, list[dict]] = defaultdict(list)

    for chunk_result in chunk_results:
        for agenda in chunk_result.get("agendas", []):
            evidence = agenda.get("evidence", [])
            topic_id = _find_topic_for_evidence(evidence, topics) or "unknown"
            by_topic[topic_id].append(agenda)

    # 2. 각 토픽 내에서만 중복 검사 (범위 축소 = 정확도 향상)
    merged_items: list[dict] = []

    for items in by_topic.values():
        if len(items) == 1:
            merged_items.extend(items)
        else:
            # 같은 토픽 내 항목만 병합 시도
            merged = _merge_within_topic(items)
            merged_items.extend(merged)

    # 3. 시간순 정렬 (첫 번째 evidence의 start_utt_id 기준)
    def _get_min_turn(agenda: dict) -> int:
        evidence = agenda.get("evidence", [])
        if not evidence:
            return 0
        first_evidence = evidence[0]
        start_ms = first_evidence.get("start_ms")
        if isinstance(start_ms, int):
            return start_ms
        start_utt_id = str(first_evidence.get("start_utt_id", "0"))
        try:
            if start_utt_id.startswith("utt-"):
                return int(start_utt_id.split("-")[1])
            return int(start_utt_id)
        except (ValueError, IndexError):
            return 0

    merged_items.sort(key=_get_min_turn)

    return merged_items


def _get_evidence_utt_ids(agenda: dict) -> set[str]:
    """아젠다의 evidence에서 utterance ID 집합 추출."""
    ids: set[str] = set()
    for ev in agenda.get("evidence", []):
        start = str(ev.get("start_utt_id", "")).strip()
        end = str(ev.get("end_utt_id", "")).strip()
        if start:
            ids.add(start)
        if end:
            ids.add(end)
    return ids


def _calculate_evidence_overlap(ids1: set[str], ids2: set[str]) -> float:
    """두 evidence 집합의 overlap 비율 계산.

    Returns:
        overlap 비율 (0.0 ~ 1.0). min(len)이 0이면 0.0 반환.
    """
    if not ids1 or not ids2:
        return 0.0
    intersection = len(ids1 & ids2)
    min_size = min(len(ids1), len(ids2))
    return intersection / min_size if min_size > 0 else 0.0


def _extract_topic_keywords(topic: str) -> set[str]:
    """토픽 문자열에서 의미있는 키워드 추출.

    공백/특수문자로 분리 후 불용어 제거, 2자 이상 단어만 유지.
    """
    import re

    # 공백 및 특수문자로 분리
    words = re.split(r"[\s,./()·\-_]+", topic.lower().strip())

    # 불용어 제거, 2자 이상만 유지
    keywords = {
        word for word in words
        if len(word) >= 2 and word not in KOREAN_STOPWORDS
    }
    return keywords


def _calculate_topic_similarity(topic1: str, topic2: str) -> float:
    """두 토픽의 키워드 유사도 계산.

    Returns:
        유사도 (0.0 ~ 1.0). 키워드가 없으면 0.0 반환.
    """
    kw1 = _extract_topic_keywords(topic1)
    kw2 = _extract_topic_keywords(topic2)

    if not kw1 or not kw2:
        return 0.0

    intersection = len(kw1 & kw2)
    min_size = min(len(kw1), len(kw2))
    return intersection / min_size if min_size > 0 else 0.0


def _merge_two_agendas(primary: dict, secondary: dict) -> dict:
    """두 아젠다를 병합 (primary 기준)."""
    result = primary.copy()

    # description은 더 긴 쪽 유지
    if len(str(secondary.get("description", ""))) > len(str(result.get("description", ""))):
        result["description"] = secondary.get("description", "")

    # evidence union
    existing_evidence = list(result.get("evidence", []) or [])
    incoming_evidence = list(secondary.get("evidence", []) or [])
    seen = {
        (str(item.get("start_utt_id")), str(item.get("end_utt_id")))
        for item in existing_evidence
    }
    for item in incoming_evidence:
        key_tuple = (str(item.get("start_utt_id")), str(item.get("end_utt_id")))
        if key_tuple not in seen:
            existing_evidence.append(item)
            seen.add(key_tuple)
    result["evidence"] = existing_evidence

    # decision 병합
    existing_decision = result.get("decision")
    incoming_decision = secondary.get("decision")
    if not existing_decision and incoming_decision:
        result["decision"] = incoming_decision
    elif existing_decision and incoming_decision:
        _merge_decision_evidence(existing_decision, incoming_decision)

    return result


def _merge_within_topic(items: list[dict]) -> list[dict]:
    """같은 토픽 내 중복 아젠다 병합 (evidence overlap + topic 유사도 기반).

    다음 조건 중 하나라도 만족하면 동일 주제로 간주하여 병합:
    1. Evidence ID가 50% 이상 겹침 (같은 발화 근거)
    2. Topic 키워드가 50% 이상 겹침 (의미적 유사)
    """
    if len(items) <= 1:
        return items

    merged: list[dict] = []
    used: set[int] = set()

    for i, agenda_a in enumerate(items):
        if i in used:
            continue

        ids_a = _get_evidence_utt_ids(agenda_a)
        topic_a = str(agenda_a.get("topic", "")).strip()
        current = agenda_a.copy()
        used.add(i)

        # 나머지 아젠다와 병합 조건 검사
        for j in range(i + 1, len(items)):
            if j in used:
                continue

            agenda_b = items[j]
            ids_b = _get_evidence_utt_ids(agenda_b)
            topic_b = str(agenda_b.get("topic", "")).strip()

            # 조건 1: Evidence overlap
            evidence_overlap = _calculate_evidence_overlap(ids_a, ids_b)
            should_merge_by_evidence = evidence_overlap >= EVIDENCE_OVERLAP_MERGE_THRESHOLD

            # 조건 2: Topic 키워드 유사도
            topic_similarity = _calculate_topic_similarity(topic_a, topic_b)
            should_merge_by_topic = topic_similarity >= TOPIC_KEYWORD_OVERLAP_THRESHOLD

            # 둘 중 하나라도 만족하면 병합
            if should_merge_by_evidence or should_merge_by_topic:
                merge_reason = []
                if should_merge_by_evidence:
                    merge_reason.append(f"evidence={evidence_overlap*100:.0f}%")
                if should_merge_by_topic:
                    merge_reason.append(f"topic={topic_similarity*100:.0f}%")

                logger.info(
                    "Merging agendas: '%s' + '%s' (%s)",
                    topic_a[:25],
                    topic_b[:25],
                    ", ".join(merge_reason),
                )
                current = _merge_two_agendas(current, agenda_b)
                # 병합 후 evidence IDs 업데이트
                ids_a = _get_evidence_utt_ids(current)
                used.add(j)

        merged.append(current)

    return merged


def _merge_decision_evidence(existing: dict, incoming: dict) -> None:
    """두 decision의 evidence를 병합 (in-place)."""
    ex_evidence = list(existing.get("evidence", []) or [])
    in_evidence = list(incoming.get("evidence", []) or [])
    ex_seen = {
        (str(item.get("start_utt_id")), str(item.get("end_utt_id")))
        for item in ex_evidence
    }
    for item in in_evidence:
        key_tuple = (str(item.get("start_utt_id")), str(item.get("end_utt_id")))
        if key_tuple not in ex_seen:
            ex_evidence.append(item)
            ex_seen.add(key_tuple)
    existing["evidence"] = ex_evidence


def _merge_chunk_results_simple(chunk_results: list[dict]) -> list[dict]:
    """단순 문자열 키 기반 병합 (토픽 없을 때 fallback)."""
    merged_by_topic: OrderedDict[str, dict] = OrderedDict()

    for chunk_result in chunk_results:
        for agenda in chunk_result.get("agendas", []):
            topic = str(agenda.get("topic", "")).strip()
            if not topic:
                continue
            key = " ".join(topic.lower().split())

            if key not in merged_by_topic:
                merged_by_topic[key] = agenda.copy()
                continue

            existing = merged_by_topic[key]

            if len(str(agenda.get("description", ""))) > len(str(existing.get("description", ""))):
                existing["description"] = agenda.get("description", "")

            existing_evidence = list(existing.get("evidence", []) or [])
            incoming_evidence = list(agenda.get("evidence", []) or [])
            seen = {
                (str(item.get("start_utt_id")), str(item.get("end_utt_id")))
                for item in existing_evidence
            }
            for item in incoming_evidence:
                key_tuple = (str(item.get("start_utt_id")), str(item.get("end_utt_id")))
                if key_tuple not in seen:
                    existing_evidence.append(item)
                    seen.add(key_tuple)
            existing["evidence"] = existing_evidence

            existing_decision = existing.get("decision")
            incoming_decision = agenda.get("decision")
            if not existing_decision and incoming_decision:
                existing["decision"] = incoming_decision
            elif existing_decision and incoming_decision:
                _merge_decision_evidence(existing_decision, incoming_decision)

    return list(merged_by_topic.values())


def _build_llm_merge_candidates(
    chunk_results: list[dict],
) -> tuple[list[dict], dict[str, dict], dict[str, int]]:
    """LLM 병합용 후보 agenda 목록/맵 생성."""
    candidates: list[dict] = []
    agenda_by_id: dict[str, dict] = {}
    agenda_order: dict[str, int] = {}

    running_index = 0
    for chunk_idx, chunk_result in enumerate(chunk_results):
        for agenda_idx, agenda in enumerate(chunk_result.get("agendas", [])):
            agenda_id = f"a{running_index}"
            running_index += 1

            decision = agenda.get("decision") or {}
            evidence = list(agenda.get("evidence", []) or [])
            first_evidence = evidence[0] if evidence else {}

            candidates.append({
                "agenda_id": agenda_id,
                "chunk_index": chunk_idx,
                "agenda_index": agenda_idx,
                "topic": str(agenda.get("topic", "")),
                "description": str(agenda.get("description", "")),
                "decision_content": str(decision.get("content", "")) if decision else "",
                "decision_context": str(decision.get("context", "")) if decision else "",
                "topic_id_hint": str(first_evidence.get("topic_id", "") or ""),
                "evidence_count": len(evidence),
            })
            agenda_by_id[agenda_id] = agenda
            agenda_order[agenda_id] = len(agenda_order)

    return candidates, agenda_by_id, agenda_order


def _invoke_merge_chain(
    chunk_agendas_text: str,
    realtime_topics_text: str,
) -> AgendaMergeOutput:
    """LLM 기반 agenda 병합 그룹 생성."""
    parser = PydanticOutputParser(pydantic_object=AgendaMergeOutput)
    prompt = ChatPromptTemplate.from_template(AGENDA_MERGE_PROMPT)
    chain = prompt | get_pr_generator_llm() | parser

    return chain.invoke({
        "realtime_topics": realtime_topics_text,
        "chunk_agendas": chunk_agendas_text,
        "format_instructions": parser.get_format_instructions(),
    })


def _materialize_merged_agenda(
    source_agenda_ids: list[str],
    agenda_by_id: dict[str, dict],
    merged_topic: str = "",
    merged_description: str = "",
    merged_decision_content: str | None = None,
    merged_decision_context: str | None = None,
) -> dict | None:
    """source_agenda_ids를 실제 agenda로 병합하고, LLM이 제안한 문구를 반영."""
    if not source_agenda_ids:
        return None

    first_id = source_agenda_ids[0]
    current = agenda_by_id[first_id].copy()

    for agenda_id in source_agenda_ids[1:]:
        current = _merge_two_agendas(current, agenda_by_id[agenda_id])

    topic_text = merged_topic.strip()
    if topic_text:
        current["topic"] = topic_text

    description_text = merged_description.strip()
    if description_text:
        current["description"] = description_text

    # decision 문구는 LLM 결과를 우선하되, evidence는 기존 union 결과를 유지한다.
    if merged_decision_content is not None:
        decision_text = merged_decision_content.strip()
        if not decision_text:
            current["decision"] = None
        else:
            decision_context = (merged_decision_context or "").strip()
            decision_evidence = []
            if isinstance(current.get("decision"), dict):
                decision_evidence = list(current["decision"].get("evidence", []) or [])
            if not decision_evidence:
                decision_evidence = list(current.get("evidence", []) or [])

            current["decision"] = {
                "content": decision_text,
                "context": decision_context,
                "evidence": decision_evidence,
            }

    return current


def _merge_chunk_results_with_llm(
    chunk_results: list[dict],
    topics: list[dict],
) -> list[dict]:
    """청크 결과를 LLM으로 병합한다. 실패 시 규칙 병합으로 fallback."""
    candidates, agenda_by_id, agenda_order = _build_llm_merge_candidates(chunk_results)
    if len(candidates) <= 1:
        return list(agenda_by_id.values())

    topics_text = _format_realtime_topics_for_prompt(topics)
    chunk_agendas_text = json.dumps(candidates, ensure_ascii=False)

    try:
        merge_output = _invoke_merge_chain(chunk_agendas_text, topics_text)
    except Exception as e:
        logger.warning("LLM merge failed, fallback to rule merge: %s", e)
        return _merge_chunk_results_with_topics(chunk_results, topics)

    used_ids: set[str] = set()
    merged_with_order: list[tuple[int, dict]] = []

    for group in merge_output.merged_agendas:
        source_ids: list[str] = []
        for agenda_id in group.source_agenda_ids:
            if agenda_id in agenda_by_id and agenda_id not in used_ids:
                source_ids.append(agenda_id)
                used_ids.add(agenda_id)

        if not source_ids:
            continue

        merged_agenda = _materialize_merged_agenda(
            source_agenda_ids=source_ids,
            agenda_by_id=agenda_by_id,
            merged_topic=group.merged_topic,
            merged_description=group.merged_description,
            merged_decision_content=group.merged_decision_content,
            merged_decision_context=group.merged_decision_context,
        )
        if not merged_agenda:
            continue

        min_order = min(agenda_order[agenda_id] for agenda_id in source_ids)
        merged_with_order.append((min_order, merged_agenda))

    # LLM 출력 누락 대비: 미할당 agenda는 singleton으로 추가한다.
    for agenda_id, agenda in agenda_by_id.items():
        if agenda_id in used_ids:
            continue
        merged_with_order.append((agenda_order[agenda_id], agenda.copy()))

    merged_with_order.sort(key=lambda item: item[0])
    merged_agendas = [agenda for _, agenda in merged_with_order]

    logger.info(
        "LLM merge finished: input=%d, output=%d",
        len(candidates),
        len(merged_agendas),
    )
    return merged_agendas


# =============================================================================
# Evidence 처리
# =============================================================================


def _apply_fallback_evidence(
    result: ExtractionOutput,
    fallback_span: list[dict],
    topic_id: str | None = None,
    topic_name: str | None = None,
    allow_fallback: bool = True,
) -> list[dict]:
    """LLM 결과에 fallback evidence 적용 및 topic 정보 추가."""
    agendas: list[dict] = []
    agenda_fallback_count = 0
    decision_fallback_count = 0

    for agenda in result.agendas:
        # Agenda evidence
        agenda_evidence = []
        if agenda.evidence:
            for span in agenda.evidence:
                span_dict = span.model_dump()
                # topic 정보가 없으면 fallback으로 주입
                if not span_dict.get("topic_id") and topic_id:
                    span_dict["topic_id"] = topic_id
                if not span_dict.get("topic_name") and topic_name:
                    span_dict["topic_name"] = topic_name
                agenda_evidence.append(span_dict)
        elif allow_fallback:
            agenda_evidence = fallback_span
            agenda_fallback_count += 1

        # Decision evidence
        decision_data = None
        if agenda.decision:
            decision_evidence = []
            if agenda.decision.evidence:
                for span in agenda.decision.evidence:
                    span_dict = span.model_dump()
                    if not span_dict.get("topic_id") and topic_id:
                        span_dict["topic_id"] = topic_id
                    if not span_dict.get("topic_name") and topic_name:
                        span_dict["topic_name"] = topic_name
                    decision_evidence.append(span_dict)
            else:
                decision_evidence = agenda_evidence
                if allow_fallback and agenda_evidence == fallback_span:
                    decision_fallback_count += 1

            decision_data = {
                "content": agenda.decision.content,
                "context": agenda.decision.context,
                "evidence": decision_evidence,
            }

        agendas.append({
            "topic": agenda.topic,
            "description": agenda.description,
            "evidence": agenda_evidence,
            "decision": decision_data,
        })

    if allow_fallback and (agenda_fallback_count or decision_fallback_count):
        logger.info(
            "Evidence fallback applied: agenda_fallback=%d, decision_fallback=%d, agendas=%d",
            agenda_fallback_count,
            decision_fallback_count,
            len(result.agendas),
        )

    return agendas


# =============================================================================
# LLM 호출
# =============================================================================


def _invoke_chain(
    transcript_text: str,
    realtime_topics_text: str,
) -> ExtractionOutput:
    """LLM 체인 호출."""
    parser = PydanticOutputParser(pydantic_object=ExtractionOutput)
    prompt = ChatPromptTemplate.from_template(AGENDA_EXTRACTION_PROMPT)
    chain = prompt | get_pr_generator_llm() | parser

    return chain.invoke({
        "realtime_topics": realtime_topics_text,
        "transcript": transcript_text,
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


async def _invoke_chain_with_retry(
    transcript_text: str,
    realtime_topics_text: str,
    chunk_index: int,
) -> ExtractionOutput:
    """청크 추출 호출 (rate-limit 완화를 위한 재시도 포함)."""
    last_error: Exception | None = None
    for attempt in range(1, CHUNK_MAX_RETRIES + 1):
        try:
            return _invoke_chain(transcript_text, realtime_topics_text)
        except Exception as error:
            last_error = error
            if attempt >= CHUNK_MAX_RETRIES:
                break

            if _is_rate_limit_error(error):
                backoff = min(
                    CHUNK_RATE_LIMIT_BACKOFF_BASE_SEC * (2 ** (attempt - 1)),
                    CHUNK_RATE_LIMIT_BACKOFF_MAX_SEC,
                )
                backoff += random.uniform(0.0, 1.5)
                logger.warning(
                    "Chunk extraction rate-limited: idx=%d attempt=%d/%d backoff=%.1fs",
                    chunk_index,
                    attempt,
                    CHUNK_MAX_RETRIES,
                    backoff,
                )
            else:
                backoff = float(attempt)
                backoff += random.uniform(0.0, 0.5)
                logger.warning(
                    "Chunk extraction retrying: idx=%d attempt=%d/%d backoff=%.1fs error=%s",
                    chunk_index,
                    attempt,
                    CHUNK_MAX_RETRIES,
                    backoff,
                    error,
                )

            await asyncio.sleep(backoff)

    if last_error:
        raise last_error
    raise RuntimeError("Chunk extraction failed without explicit error")


async def _refine_summary_with_llm(
    chunk_summaries: list[str],
    realtime_topics: list[dict],
    merged_agendas: list[dict],
) -> str:
    """청크 요약들을 LLM으로 통합하여 최종 요약 생성."""
    if not chunk_summaries:
        return ""

    # 단일 청크면 정제 없이 반환
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    # 청크 요약 포맷팅
    summaries_text = "\n".join(
        f"[청크 {i+1}] {summary}"
        for i, summary in enumerate(chunk_summaries)
        if summary.strip()
    )

    # 토픽 컨텍스트
    topics_text = _format_realtime_topics_for_prompt(realtime_topics)

    # 아젠다 목록 포맷팅
    agenda_lines = []
    for i, agenda in enumerate(merged_agendas, 1):
        topic = agenda.get("topic", "")
        decision = agenda.get("decision")
        decision_text = f" → 결정: {decision.get('content', '')}" if decision else ""
        agenda_lines.append(f"{i}. {topic}{decision_text}")
    agenda_list_text = "\n".join(agenda_lines) if agenda_lines else "(없음)"

    try:
        prompt = ChatPromptTemplate.from_template(SUMMARY_REFINEMENT_PROMPT)
        chain = prompt | get_pr_generator_llm()

        result = await chain.ainvoke({
            "realtime_topics": topics_text,
            "chunk_summaries": summaries_text,
            "agenda_list": agenda_list_text,
        })

        refined_summary = str(result.content).strip()
        logger.info(
            "Summary refined: chunks=%d, length=%d->%d",
            len(chunk_summaries),
            sum(len(s) for s in chunk_summaries),
            len(refined_summary),
        )
        return refined_summary

    except Exception as e:
        logger.warning("Summary refinement failed, using concatenated: %s", e)
        # 실패 시 기존 방식으로 fallback
        return " ".join(dict.fromkeys(chunk_summaries))


# =============================================================================
# 추출 노드
# =============================================================================


async def extract_single(state: GeneratePrState) -> GeneratePrState:
    """짧은 회의 추출: single pass."""
    utterances = _prepare_utterances(state)
    if not utterances:
        logger.warning("트랜스크립트가 비어있습니다")
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")

    transcript_text = _format_utterances_for_prompt(utterances)
    realtime_topics = state.get("generate_pr_realtime_topics", []) or []
    topics_text = _format_realtime_topics_for_prompt(realtime_topics)
    fallback_span = _build_chunk_span(utterances)

    try:
        result = _invoke_chain(transcript_text, topics_text)
        agendas = _apply_fallback_evidence(result, fallback_span, allow_fallback=False)
        return GeneratePrState(
            generate_pr_agendas=agendas,
            generate_pr_summary=result.summary,
            generate_pr_chunks=[{
                "index": 0,
                "utterance_count": len(utterances),
            }],
        )
    except Exception as e:
        logger.error("Single pass extraction failed: %s", e)
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")


async def extract_chunked(state: GeneratePrState) -> GeneratePrState:
    """긴 회의 추출: 3청크(50% overlap) pass."""
    utterances = _prepare_utterances(state)
    if not utterances:
        logger.warning("트랜스크립트가 비어있습니다")
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")

    realtime_topics = list(state.get("generate_pr_realtime_topics", []) or [])

    # 토픽 유무와 무관하게 3청크(50% overlap) 생성
    chunks = _create_three_overlap_chunks(utterances, realtime_topics)

    if len(chunks) <= 1:
        return await extract_single(state)

    logger.info(
        "Three-chunk extraction: chunks=%d, topics=%d",
        len(chunks),
        len(realtime_topics),
    )

    chunk_results: list[dict] = []
    chunk_meta: list[dict] = []

    for chunk_idx, chunk in enumerate(chunks):
        main_text = _format_utterances_for_prompt(chunk.utterances)
        transcript_text = main_text

        # 청크에 해당하는 토픽 컨텍스트
        topics_text = chunk.topics_context or _format_realtime_topics_for_prompt(
            [t for t in realtime_topics if str(t.get("id", "")) in chunk.topic_ids]
        )

        # Fallback span에 topic 정보 포함
        primary_topic_id = chunk.topic_ids[0] if chunk.topic_ids else None
        primary_topic_name = None
        if primary_topic_id:
            for t in realtime_topics:
                if str(t.get("id", "")) == primary_topic_id:
                    primary_topic_name = str(t.get("name", ""))
                    break

        fallback_span = _build_chunk_span(
            chunk.utterances,
            topic_id=primary_topic_id,
            topic_name=primary_topic_name,
        )

        try:
            result = await _invoke_chain_with_retry(
                transcript_text,
                topics_text,
                chunk.index,
            )
            chunk_agendas = _apply_fallback_evidence(
                result, fallback_span,
                topic_id=primary_topic_id,
                topic_name=primary_topic_name,
                allow_fallback=False,
            )

            agendas_with_evidence = sum(
                1 for agenda in chunk_agendas if agenda.get("evidence")
            )
            decisions_with_evidence = sum(
                1
                for agenda in chunk_agendas
                if agenda.get("decision") and agenda["decision"].get("evidence")
            )
            logger.info(
                "Chunk evidence extraction: idx=%d agendas=%d agendas_with_evidence=%d decisions_with_evidence=%d",
                chunk.index,
                len(chunk_agendas),
                agendas_with_evidence,
                decisions_with_evidence,
            )

            chunk_results.append({
                "summary": result.summary,
                "agendas": chunk_agendas,
            })
            chunk_meta.append({
                "index": chunk.index,
                "utterance_count": len(chunk.utterances),
                "topic_ids": chunk.topic_ids,
            })
        except Exception as e:
            logger.warning("Chunk extraction failed: idx=%d error=%s", chunk.index, e)

        if chunk_idx < len(chunks) - 1:
            await asyncio.sleep(CHUNK_REQUEST_DELAY_SEC)

    if not chunk_results:
        return GeneratePrState(generate_pr_agendas=[], generate_pr_summary="")

    # LLM 기반 병합 (실패 시 규칙 병합 fallback)
    merged_agendas = _merge_chunk_results_with_llm(
        chunk_results, realtime_topics
    )

    # 청크 요약들 추출
    chunk_summaries = [
        str(cr.get("summary", "")).strip()
        for cr in chunk_results
        if str(cr.get("summary", "")).strip()
    ]

    # LLM으로 최종 요약 정제
    refined_summary = await _refine_summary_with_llm(
        chunk_summaries=chunk_summaries,
        realtime_topics=realtime_topics,
        merged_agendas=merged_agendas,
    )

    return GeneratePrState(
        generate_pr_agendas=merged_agendas,
        generate_pr_summary=refined_summary,
        generate_pr_chunks=chunk_meta,
    )


async def extract_agendas(state: GeneratePrState) -> GeneratePrState:
    """하위 호환용 진입점: 기존 extractor 호출은 single pass로 처리."""
    return await extract_single(state)
