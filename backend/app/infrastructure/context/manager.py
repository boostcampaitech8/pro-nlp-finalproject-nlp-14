"""ContextManager - 실시간 회의 컨텍스트 관리자

책임:
1. DB(transcripts)에서 발화 데이터 로드 (읽기 전용)
2. 토픽 전환 감지 및 L1 요약 생성 (메모리 내 처리)
3. 에이전트 호출 시 적절한 컨텍스트 조합 제공

상태 관리:
- DB는 읽기 전용 (transcripts 테이블이 SSOT)
- L0/L1은 에이전트 호출 시점에 메모리에서 on-demand 생성
- 저장 없이 매 호출마다 fresh하게 구성
"""

import asyncio
import json
import logging
import uuid as uuid_module
from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.models import TopicSegment, Utterance
from app.infrastructure.context.prompts.topic_merging import TOPIC_MERGE_PROMPT
from app.infrastructure.context.prompts.topic_separation import (
    RECURSIVE_TOPIC_SEPARATION_PROMPT,
    TOPIC_SEPARATION_PROMPT,
)
from app.infrastructure.context.speaker_context import SpeakerContext

# 인메모리 임베딩용 (lazy import)
try:
    import numpy as np
    from app.infrastructure.context.embedding import TopicEmbedder

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    np = None  # type: ignore
    TopicEmbedder = None  # type: ignore

logger = logging.getLogger(__name__)

class ContextManager:
    """실시간 회의 컨텍스트 관리자 (Topic-Segmented, Read-Only DB)

    책임:
    1. DB(transcripts)에서 발화 로드 및 L0 버퍼링
    2. 토픽 전환 감지 및 L1 요약 생성 (메모리 내)
    3. 에이전트 호출 시 컨텍스트 제공

    데이터 흐름:
    - load_from_db() → L0 버퍼 구성 + L1 청크 큐잉
    - await_pending_l1() → L1 요약 병렬 생성
    - 저장 없음 (transcripts가 유일한 SSOT)
    """

    def __init__(
        self,
        meeting_id: str,
        config: ContextConfig | None = None,
        db_session: AsyncSession | None = None,
    ):
        self.meeting_id = meeting_id
        self.config = config or ContextConfig()
        self._db = db_session
        self._llm_enabled = bool(get_settings().ncp_clovastudio_api_key)

        # 인메모리 임베딩 (시맨틱 서치용)
        self._embedder = TopicEmbedder() if EMBEDDING_AVAILABLE else None
        self._topic_embeddings: dict[str, list[float]] = {}  # topic_id -> embedding

        # L0: Raw Window (고정 크기)
        self.l0_buffer: deque[Utterance] = deque(maxlen=self.config.l0_max_turns)
        self.current_topic: str = "Intro"  # 초기 토픽

        # L0: Topic Buffer (현재 토픽 발화, 제한 있음 - 무한 증식 방지)
        self.l0_topic_buffer: deque[Utterance] = deque(
            maxlen=self.config.l0_topic_buffer_max_turns
        )

        # L1: Topic Segments
        self.l1_segments: list[TopicSegment] = []

        # 반복 요약 방지: 마지막으로 요약에 포함된 발화 ID
        self._last_summarized_utterance_id: int | None = None

        # 화자 컨텍스트 관리
        self._speaker_context = SpeakerContext(
            max_buffer_per_speaker=self.config.speaker_buffer_max_per_speaker
        )

        self._pending_l1_chunks: list[list[Utterance]] = []  # 요약 대기 청크
        self._l1_task: asyncio.Task | None = None
        self._l1_processing: bool = False

    async def add_utterance(self, utterance: Utterance) -> None:
        """새 발화 추가 (L1은 비동기 처리)

        Args:
            utterance: STT로 받은 발화 데이터
        """
        # 현재 토픽 할당
        utterance_with_topic = utterance.model_copy(update={"topic": self.current_topic})

        # L0 버퍼에 추가
        self.l0_buffer.append(utterance_with_topic)
        self.l0_topic_buffer.append(utterance_with_topic)

        # 화자 컨텍스트 업데이트
        self._speaker_context.add_utterance(utterance_with_topic)

        # L1 업데이트 필요 여부 확인 (25턴마다)
        should_queue = self._should_queue_l1()
        if should_queue:
            # 현재 토픽 버퍼를 청크로 저장하고 비동기 처리 시작
            self._queue_l1_chunk()

        logger.debug(
            f"Utterance added: {utterance.speaker_name}: {utterance.text[:50]}..."
        )

    def _should_queue_l1(self) -> bool:
        """L1 청크 큐잉 필요 여부 판단 (25턴 단위).

        키워드 감지 없이 순수하게 25턴마다 토픽 분할 요약을 트리거합니다.
        """
        # 요약할 새 발화가 있는지 확인
        new_utterances = self._get_unsummarized_utterances()
        if not new_utterances:
            return False

        # 25턴 임계값 도달 시에만 트리거
        if len(new_utterances) >= self.config.l1_update_turn_threshold:
            return True

        return False

    def _queue_l1_chunk(self) -> None:
        """현재 토픽 버퍼를 L1 처리 큐에 추가"""
        utterances_to_queue = self._get_unsummarized_utterances()
        if not utterances_to_queue:
            return

        # 청크 저장
        self._pending_l1_chunks.append(list(utterances_to_queue))

        # 마지막 발화 ID 업데이트 (반복 요약 방지)
        self._last_summarized_utterance_id = utterances_to_queue[-1].id

        logger.info(
            f"L1 chunk queued: {len(utterances_to_queue)} utterances, "
            f"total pending: {len(self._pending_l1_chunks)}"
        )
        self._schedule_background_l1()

    def _schedule_background_l1(self) -> None:
        """대기 중인 L1 청크를 백그라운드에서 처리하도록 스케줄링."""
        if self._l1_task and not self._l1_task.done():
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 이벤트 루프가 없으면 백그라운드 처리 불가
            return

        self._l1_task = loop.create_task(self._run_l1_background())

    async def _run_l1_background(self) -> None:
        """백그라운드 L1 처리 루프."""
        if self._l1_processing:
            return

        self._l1_processing = True
        try:
            while self._pending_l1_chunks:
                await self.await_pending_l1()
                await asyncio.sleep(0)
        finally:
            self._l1_processing = False

    async def await_pending_l1(self) -> None:
        """대기 중인 모든 L1 처리 완료 대기 (에이전트 호출 전 사용)

        에이전트 호출 전에 이 메서드를 호출하여 모든 L1 요약이
        완료된 상태에서 컨텍스트를 제공합니다.

        25턴 단위로 발화를 토픽별로 분할하여 요약하고, 인메모리 임베딩을 생성합니다.
        """
        if self._l1_processing and self._l1_task and self._l1_task is not asyncio.current_task():
            await self._l1_task
            return

        if not self._pending_l1_chunks:
            logger.debug("No pending L1 chunks to process")
            return

        logger.info(f"Awaiting {len(self._pending_l1_chunks)} pending L1 chunks...")

        # 모든 대기 청크를 순차 처리 (토픽 분할은 재귀적으로 진행)
        chunks = self._pending_l1_chunks.copy()
        self._pending_l1_chunks.clear()

        # 새로 생성된 세그먼트 수집 (배치 임베딩용)
        new_segments: list[TopicSegment] = []

        for chunk_idx, chunk in enumerate(chunks):
            is_first = len(self.l1_segments) == 0 and chunk_idx == 0

            # 토픽 분할 처리 (인메모리)
            segments = await self._separate_topics_lightweight(
                chunk, is_first=is_first
            )

            # 새 세그먼트만 추가 (업데이트된 것은 이미 l1_segments에 반영됨)
            for seg in segments:
                if not self._find_segment_by_name(seg.name):
                    self.l1_segments.append(seg)
                    new_segments.append(seg)
                elif seg.id not in self._topic_embeddings:
                    # 업데이트된 세그먼트도 임베딩 필요
                    new_segments.append(seg)

            logger.info(
                f"Chunk {chunk_idx + 1}: {len(segments)} topics from "
                f"turn {chunk[0].id}~{chunk[-1].id}"
            )

        # 배치 임베딩 (병렬 API 호출)
        if new_segments:
            await self._embed_topics_batch_async(new_segments)

        # 토픽 수 초과 시 유사 토픽 병합
        await self._check_and_merge_topics()

        # 현재 토픽 업데이트
        if self.l1_segments:
            self.current_topic = self.l1_segments[-1].name

        logger.info(f"L1 processing complete: {len(self.l1_segments)} total segments")

    @property
    def has_pending_l1(self) -> bool:
        """대기 중인 L1 처리가 있는지 확인"""
        return len(self._pending_l1_chunks) > 0

    @property
    def is_l1_running(self) -> bool:
        """백그라운드 L1 작업이 실행 중인지 확인"""
        return self._l1_processing or (
            self._l1_task is not None and not self._l1_task.done()
        )

    async def await_l1_idle(self) -> None:
        """백그라운드 L1 작업 종료 후 컨텍스트를 사용하도록 대기."""
        current = asyncio.current_task()
        if self._l1_task and self._l1_task is current:
            return

        if self._l1_task and not self._l1_task.done():
            await self._l1_task

        if self._pending_l1_chunks:
            await self.await_pending_l1()

    def _get_unsummarized_utterances(self) -> list[Utterance]:
        """아직 요약되지 않은 발화 목록 반환

        _last_summarized_utterance_id 이후의 발화만 반환하여
        동일 구간 반복 요약 방지
        """
        if self._last_summarized_utterance_id is None:
            return list(self.l0_topic_buffer)

        return [
            u for u in self.l0_topic_buffer if u.id > self._last_summarized_utterance_id
        ]

    def _collect_participants(self, utterances: list[Utterance]) -> list[str]:
        """발화 목록에서 참여자 이름 추출"""
        seen: set[str] = set()
        participants: list[str] = []
        for u in utterances:
            name = u.speaker_name
            if name and name not in seen:
                seen.add(name)
                participants.append(name)
        return participants

    def _fallback_summary(
        self,
        topic_name: str,
        utterances: list[Utterance],
    ) -> str:
        """LLM 실패 시 요약 fallback"""
        if not utterances:
            return f"{topic_name} 논의 요약 없음."

        first = utterances[0].text
        last = utterances[-1].text
        return (
            f"{topic_name} 논의 {len(utterances)}턴. "
            f"시작: {first[:80]} / 마지막: {last[:80]}"
        )

    async def _call_llm(self, prompt: str) -> str | None:
        """LLM 호출 (실패 시 None 반환)

        Args:
            prompt: LLM에 전달할 프롬프트

        Note:
            HCX-DASH-002 모델 사용 (실시간 처리 + 빠른 응답)
            max_tokens=2048 (정보 손실 최소화)
        """
        if not self._llm_enabled:
            return None

        try:
            from app.infrastructure.graph.integration.llm import get_context_summarizer_llm
        except Exception as e:
            logger.debug(f"Failed to import LLM client: {e}")
            return None

        try:
            llm = get_context_summarizer_llm()
            response = await llm.ainvoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning(f"Context summarization LLM call failed: {e}")
            return None

    @staticmethod
    def _safe_json_loads(text: str) -> dict | None:
        """LLM 응답에서 JSON 파싱 (부분 추출 지원)"""
        if not text:
            return None

        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    return None
        return None

    # === 경량 토픽 분할 (메모리 전용, DB 미사용) ===

    async def _separate_topics_lightweight(
        self,
        utterances: list[Utterance],
        is_first: bool = True,
    ) -> list[TopicSegment]:
        """경량 토픽 분할 (DB/임베딩 없이 메모리에서만 처리).

        Args:
            utterances: 발화 리스트
            is_first: 첫 번째 배치 여부

        Returns:
            생성된 TopicSegment 리스트
        """
        if not utterances:
            return []

        start_turn = utterances[0].id
        end_turn = utterances[-1].id

        # 프롬프트 생성
        utterances_text = self._format_utterances_for_topic_separation(utterances)

        if is_first:
            prompt = TOPIC_SEPARATION_PROMPT.format(
                start_turn=start_turn,
                end_turn=end_turn,
                utterances=utterances_text,
            )
        else:
            existing_topics_text = self._format_existing_topics_for_prompt()
            prompt = RECURSIVE_TOPIC_SEPARATION_PROMPT.format(
                existing_topics=existing_topics_text or "(없음)",
                start_turn=start_turn,
                end_turn=end_turn,
                utterances=utterances_text,
            )

        # LLM 호출
        response = await self._call_llm(prompt)
        if not response:
            # fallback: 단일 토픽 생성
            return [self._create_fallback_segment(utterances, start_turn, end_turn)]

        if logger.isEnabledFor(logging.DEBUG):
            preview = response.replace("\n", "\\n")
            if len(preview) > 2000:
                preview = preview[:2000] + "..."
            logger.debug("Topic separation LLM response (truncated): %s", preview)

        # 응답 파싱
        segments = self._parse_topic_separation_response(
            response, utterances, start_turn, end_turn
        )

        if not segments:
            return [self._create_fallback_segment(utterances, start_turn, end_turn)]

        return segments

    def _format_utterances_for_topic_separation(
        self, utterances: list[Utterance]
    ) -> str:
        """토픽 분할용 발화 포맷팅."""
        lines: list[str] = []
        for u in utterances:
            ts = u.absolute_timestamp.strftime("%H:%M:%S")
            lines.append(f"[Turn {u.id}] [{ts}] {u.speaker_name}: {u.text}")
        return "\n".join(lines)

    def _format_existing_topics_for_prompt(self) -> str:
        """기존 토픽을 프롬프트용으로 포맷팅."""
        if not self.l1_segments:
            return ""

        lines: list[str] = []
        for seg in self.l1_segments:
            keywords_str = ", ".join(seg.keywords[:5]) if seg.keywords else ""
            summary_preview = (
                seg.summary[:200] + "..." if len(seg.summary) > 200 else seg.summary
            )
            lines.append(
                f"- **{seg.name}** (Turn {seg.start_utterance_id}~{seg.end_utterance_id}): "
                f"{summary_preview} [키워드: {keywords_str}]"
            )
        return "\n".join(lines)

    def _parse_topic_separation_response(
        self,
        response: str,
        utterances: list[Utterance],
        default_start: int,
        default_end: int,
    ) -> list[TopicSegment]:
        """토픽 분할 LLM 응답 파싱."""
        data = self._safe_json_loads(response)
        if not isinstance(data, dict):
            return []

        topics = data.get("topics")
        if not isinstance(topics, list):
            return []

        segments: list[TopicSegment] = []

        def _coerce_int(value: object, fallback: int) -> int:
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                try:
                    return int(value.strip())
                except ValueError:
                    return fallback
            return fallback

        def _coerce_bool(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return value != 0
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "yes", "y", "1"}:
                    return True
                if normalized in {"false", "no", "n", "0"}:
                    return False
            return False

        def _coerce_keywords(value: object) -> list[str]:
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            return []

        for t in topics:
            if not isinstance(t, dict):
                continue

            topic_name = t.get("topic_name")
            summary = t.get("summary")
            if not isinstance(topic_name, str) or not topic_name.strip():
                continue
            if not isinstance(summary, str) or not summary.strip():
                continue

            turn_start = _coerce_int(t.get("turn_start"), default_start)
            turn_end = _coerce_int(t.get("turn_end"), default_end)
            keywords = _coerce_keywords(t.get("keywords"))
            is_updated = _coerce_bool(t.get("is_updated", False))

            # 기존 토픽 업데이트 처리
            if is_updated:
                existing = self._find_segment_by_name(topic_name)
                if existing:
                    existing.summary = summary
                    existing.end_utterance_id = turn_end
                    existing.keywords = list(set(existing.keywords + keywords))[:10]
                    segments.append(existing)
                    continue

            # 새 토픽 생성
            segment = TopicSegment(
                id=str(uuid_module.uuid4()),
                name=topic_name,
                summary=summary,
                start_utterance_id=turn_start,
                end_utterance_id=turn_end,
                keywords=keywords,
                participants=self._collect_participants(utterances),
            )
            segments.append(segment)

        return segments

    def _find_segment_by_name(self, name: str) -> TopicSegment | None:
        """이름으로 기존 세그먼트 검색."""
        for seg in self.l1_segments:
            if seg.name == name:
                return seg
        return None

    def _create_fallback_segment(
        self,
        utterances: list[Utterance],
        start_turn: int,
        end_turn: int,
    ) -> TopicSegment:
        """Fallback 세그먼트 생성."""
        topic_name = f"Topic_{start_turn}_{end_turn}"
        if not self.l1_segments:
            topic_name = "Intro"

        return TopicSegment(
            id=str(uuid_module.uuid4()),
            name=topic_name,
            summary=self._fallback_summary(topic_name, utterances),
            start_utterance_id=start_turn,
            end_utterance_id=end_turn,
            keywords=[],
            participants=self._collect_participants(utterances),
        )

    # === 인메모리 임베딩 & 시맨틱 서치 ===

    async def _embed_topics_batch_async(self, segments: list[TopicSegment]) -> int:
        """여러 토픽을 배치로 임베딩 (비동기, 병렬 API 호출).

        Args:
            segments: 임베딩할 토픽 세그먼트 리스트

        Returns:
            int: 성공적으로 임베딩된 토픽 수
        """
        if not self._embedder or not self._embedder.is_available:
            return 0

        # 이미 임베딩된 토픽 제외
        to_embed = [
            (seg, seg.summary)
            for seg in segments
            if seg.id not in self._topic_embeddings and seg.summary.strip()
        ]

        if not to_embed:
            return 0

        texts = [summary for _, summary in to_embed]
        embeddings = await self._embedder.embed_batch_async(texts)

        embedded_count = 0
        for (seg, _), emb in zip(to_embed, embeddings):
            # 영벡터(실패)가 아닌 경우만 저장
            if emb is not None and not np.all(emb == 0):
                self._topic_embeddings[seg.id] = emb.tolist()
                embedded_count += 1

        if embedded_count > 0:
            logger.info(f"Batch embedded {embedded_count}/{len(to_embed)} topics")

        return embedded_count

    def _embed_topic(self, segment: TopicSegment) -> None:
        """토픽 요약을 임베딩하여 메모리에 저장.

        Note:
            Deprecated: _embed_topics_batch_async() 사용 권장
        """
        if not self._embedder or not self._embedder.is_available:
            return

        embedding = self._embedder.embed_text(segment.summary)
        if embedding is not None:
            self._topic_embeddings[segment.id] = embedding.tolist()
            logger.debug(f"Embedded topic '{segment.name}' (id={segment.id[:8]}...)")

    # === 토픽 병합 ===

    async def _check_and_merge_topics(self) -> None:
        """토픽 수가 max_topics 초과 시 유사 토픽 병합.

        cosine similarity가 topic_merge_threshold 이상인 토픽 쌍을 찾아 병합합니다.
        """
        if len(self.l1_segments) <= self.config.max_topics:
            return

        if not self._embedder or not self._embedder.is_available:
            logger.warning("Embedder not available, skipping topic merge")
            return

        logger.info(
            f"Topic count ({len(self.l1_segments)}) exceeds max ({self.config.max_topics}), "
            "attempting merge..."
        )

        # max_topics 이하가 될 때까지 반복 병합
        while len(self.l1_segments) > self.config.max_topics:
            merged = await self._merge_most_similar_pair()
            if not merged:
                logger.warning(
                    f"No similar topics to merge (threshold={self.config.topic_merge_threshold}), "
                    f"keeping {len(self.l1_segments)} topics"
                )
                break

    async def _merge_most_similar_pair(self) -> bool:
        """가장 유사한 토픽 쌍을 찾아 병합.

        Returns:
            bool: 병합 성공 여부
        """
        if len(self.l1_segments) < 2:
            return False

        # 유사도 행렬 계산
        best_pair: tuple[int, int] | None = None
        best_similarity = 0.0

        for i in range(len(self.l1_segments)):
            for j in range(i + 1, len(self.l1_segments)):
                seg_i = self.l1_segments[i]
                seg_j = self.l1_segments[j]

                if seg_i.id not in self._topic_embeddings:
                    continue
                if seg_j.id not in self._topic_embeddings:
                    continue

                emb_i = np.array(self._topic_embeddings[seg_i.id], dtype=np.float32)
                emb_j = np.array(self._topic_embeddings[seg_j.id], dtype=np.float32)
                similarity = self._embedder.cosine_similarity(emb_i, emb_j)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_pair = (i, j)

        # 임계값 미만이면 병합하지 않음
        if best_pair is None or best_similarity < self.config.topic_merge_threshold:
            return False

        i, j = best_pair
        seg_i = self.l1_segments[i]
        seg_j = self.l1_segments[j]

        logger.info(
            f"Merging topics: '{seg_i.name}' + '{seg_j.name}' (similarity={best_similarity:.3f})"
        )

        # LLM으로 병합 요약 생성
        merged_segment = await self._merge_topics_with_llm(seg_i, seg_j)
        if not merged_segment:
            # LLM 실패 시 단순 병합
            merged_segment = self._merge_topics_simple(seg_i, seg_j)

        # 기존 토픽 제거 (역순으로 제거해야 인덱스 오류 방지)
        del self.l1_segments[j]
        del self.l1_segments[i]

        # 임베딩 제거
        self._topic_embeddings.pop(seg_i.id, None)
        self._topic_embeddings.pop(seg_j.id, None)

        # 병합된 토픽 추가
        self.l1_segments.append(merged_segment)
        self._embed_topic(merged_segment)

        logger.info(f"Merged into: '{merged_segment.name}' (now {len(self.l1_segments)} topics)")
        return True

    async def _merge_topics_with_llm(
        self, seg1: TopicSegment, seg2: TopicSegment
    ) -> TopicSegment | None:
        """LLM을 사용하여 두 토픽 병합."""
        prompt = TOPIC_MERGE_PROMPT.format(
            topic_name_1=seg1.name,
            summary_1=seg1.summary,
            topic_name_2=seg2.name,
            summary_2=seg2.summary,
        )

        response = await self._call_llm(prompt)
        if not response:
            return None

        data = self._safe_json_loads(response)
        if not data:
            return None

        merged_name = data.get("merged_topic_name")
        merged_summary = data.get("merged_summary")
        if not merged_name or not merged_summary:
            return None

        keywords = data.get("keywords", [])
        if isinstance(keywords, list):
            keywords = [str(k) for k in keywords if k][:10]
        else:
            keywords = []

        # 병합된 키워드 (기존 + 새로운)
        all_keywords = list(set(seg1.keywords + seg2.keywords + keywords))[:10]

        return TopicSegment(
            id=str(uuid_module.uuid4()),
            name=merged_name,
            summary=merged_summary,
            start_utterance_id=min(seg1.start_utterance_id, seg2.start_utterance_id),
            end_utterance_id=max(seg1.end_utterance_id, seg2.end_utterance_id),
            keywords=all_keywords,
            participants=list(set(seg1.participants + seg2.participants)),
        )

    def _merge_topics_simple(
        self, seg1: TopicSegment, seg2: TopicSegment
    ) -> TopicSegment:
        """단순 병합 (LLM 실패 시 fallback)."""
        # 시간순으로 정렬
        if seg1.start_utterance_id > seg2.start_utterance_id:
            seg1, seg2 = seg2, seg1

        merged_name = f"{seg1.name} & {seg2.name}"
        if len(merged_name) > 30:
            merged_name = seg1.name  # 첫 번째 토픽명 사용

        merged_summary = f"{seg1.summary} 이후, {seg2.summary}"
        if len(merged_summary) > 500:
            merged_summary = f"{seg1.summary[:200]}... {seg2.summary[:200]}..."

        return TopicSegment(
            id=str(uuid_module.uuid4()),
            name=merged_name,
            summary=merged_summary,
            start_utterance_id=seg1.start_utterance_id,
            end_utterance_id=seg2.end_utterance_id,
            keywords=list(set(seg1.keywords + seg2.keywords))[:10],
            participants=list(set(seg1.participants + seg2.participants)),
        )

    async def search_similar_topics_async(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[TopicSegment]:
        """쿼리와 유사한 토픽을 비동기 시맨틱 서치.

        Args:
            query: 검색 쿼리
            top_k: 최대 반환 개수
            threshold: 최소 유사도 임계값

        Returns:
            유사도 순으로 정렬된 TopicSegment 리스트
        """
        if not self._embedder or not self._embedder.is_available:
            logger.debug("Embedder not available, returning recent topics")
            return self.l1_segments[:top_k]

        if not self._topic_embeddings:
            return self.l1_segments[:top_k]

        # 비동기 쿼리 임베딩 생성
        query_embedding = await self._embedder.embed_text_async(query)
        if query_embedding is None:
            return self.l1_segments[:top_k]

        # 유사도 계산
        similarities: list[tuple[TopicSegment, float]] = []
        for seg in self.l1_segments:
            if seg.id not in self._topic_embeddings:
                continue

            topic_embedding = np.array(self._topic_embeddings[seg.id], dtype=np.float32)
            similarity = self._embedder.cosine_similarity(query_embedding, topic_embedding)

            if similarity >= threshold:
                similarities.append((seg, similarity))

        # 유사도 내림차순 정렬
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Top-K 반환
        results = [seg for seg, _ in similarities[:top_k]]
        logger.debug(
            f"Async semantic search for '{query[:30]}...': "
            f"found {len(results)} topics (top_k={top_k}, threshold={threshold})"
        )
        return results

    def search_similar_topics(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[TopicSegment]:
        """쿼리와 유사한 토픽을 시맨틱 서치 (동기, 하위 호환성).

        Note:
            search_similar_topics_async() 사용 권장

        Args:
            query: 검색 쿼리
            top_k: 최대 반환 개수
            threshold: 최소 유사도 임계값

        Returns:
            유사도 순으로 정렬된 TopicSegment 리스트
        """
        if not self._embedder or not self._embedder.is_available:
            # 임베딩 미사용 시 전체 반환
            logger.debug("Embedder not available, returning all topics")
            return self.l1_segments[:top_k]

        if not self._topic_embeddings:
            return self.l1_segments[:top_k]

        # 쿼리 임베딩 생성
        query_embedding = self._embedder.embed_text(query)
        if query_embedding is None:
            return self.l1_segments[:top_k]

        # 유사도 계산
        similarities: list[tuple[TopicSegment, float]] = []
        for seg in self.l1_segments:
            if seg.id not in self._topic_embeddings:
                continue

            topic_embedding = np.array(self._topic_embeddings[seg.id], dtype=np.float32)
            similarity = self._embedder.cosine_similarity(query_embedding, topic_embedding)

            if similarity >= threshold:
                similarities.append((seg, similarity))

        # 유사도 내림차순 정렬
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Top-K 반환
        results = [seg for seg, _ in similarities[:top_k]]
        logger.debug(
            f"Semantic search for '{query[:30]}...': "
            f"found {len(results)} topics (top_k={top_k}, threshold={threshold})"
        )
        return results

    def get_topic_by_keywords(self, keywords: list[str]) -> list[TopicSegment]:
        """키워드로 토픽 검색 (fallback용).

        Args:
            keywords: 검색할 키워드 리스트

        Returns:
            매칭된 TopicSegment 리스트
        """
        if not keywords:
            return []

        results: list[TopicSegment] = []
        keywords_lower = [kw.lower() for kw in keywords]

        for seg in self.l1_segments:
            # 토픽명, 요약, 키워드에서 검색
            seg_text = f"{seg.name} {seg.summary} {' '.join(seg.keywords)}".lower()
            if any(kw in seg_text for kw in keywords_lower):
                results.append(seg)

        return results

    # === Public API ===

    def get_l0_utterances(self, limit: int | None = None) -> list[Utterance]:
        """L0 발화 목록 반환"""
        utterances = list(self.l0_buffer)
        if limit:
            return utterances[-limit:]
        return utterances

    def get_topic_utterances(self) -> list[Utterance]:
        """현재 토픽의 전체 발화 반환"""
        return list(self.l0_topic_buffer)

    def get_l1_segments(self) -> list[TopicSegment]:
        """L1 토픽 세그먼트 반환"""
        return self.l1_segments.copy()

    def get_topic_flow(self) -> list[str]:
        """토픽 흐름 반환"""
        return [segment.name for segment in self.l1_segments]

    def get_context_snapshot(self) -> dict:
        """디버깅용 스냅샷"""
        return {
            "meeting_id": self.meeting_id,
            "current_topic": self.current_topic,
            "l0_buffer_size": len(self.l0_buffer),
            "l0_topic_buffer_size": len(self.l0_topic_buffer),
            "l1_segments_count": len(self.l1_segments),
            "speakers": self._speaker_context.get_all_speakers(),
        }

    @property
    def recent_utterances(self) -> list[Utterance]:
        """호환성용 프로퍼티"""
        return list(self.l0_buffer)

    @property
    def speaker_context(self) -> SpeakerContext:
        """화자 컨텍스트 접근"""
        return self._speaker_context

    @property
    def embedding_available(self) -> bool:
        """임베딩 사용 가능 여부"""
        return self._embedder is not None and self._embedder.is_available

    # === 토픽 수동 제어 ===

    async def force_topic_change(self, new_topic_name: str) -> None:
        """수동 토픽 전환

        현재 토픽 버퍼를 L1 청크로 큐잉하고 새 토픽으로 전환합니다.
        """
        if self.l0_topic_buffer:
            self._queue_l1_chunk()
            self.l0_topic_buffer.clear()
        self.current_topic = new_topic_name
        logger.info(f"Manual topic change to: {new_topic_name}")

    async def load_from_db(self, limit: int | None = None, build_l1: bool = True) -> int:
        """DB(transcripts 테이블)에서 발화 데이터 로드하여 L0/L1 구성

        에이전트 호출 시점에 호출하여 최신 컨텍스트를 메모리에 구성합니다.
        L0는 항상 최근 25개 턴을 유지합니다 (deque maxlen으로 자동 관리).
        L1은 비동기 배치 처리로 빠르게 생성합니다.

        Args:
            limit: 최대 로드 발화 수 (None이면 전체)
            build_l1: L1 세그먼트도 생성할지 여부 (기본 True)

        Returns:
            int: 로드된 발화 수
        """
        if not self._db:
            logger.warning("DB session not provided, skipping load_from_db")
            return 0

        from app.models.transcript import Transcript

        query = (
            select(Transcript)
            .where(Transcript.meeting_id == UUID(self.meeting_id))
            .order_by(Transcript.start_ms)
        )
        if limit:
            query = query.limit(limit)

        result = await self._db.execute(query)
        rows = result.scalars().all()

        # 1단계: 모든 발화를 L0 버퍼에 로드
        utterances: list[Utterance] = []
        for i, row in enumerate(rows):
            utterance = Utterance(
                id=i + 1,
                speaker_id=str(row.user_id),
                speaker_name="",  # TODO: user 테이블 조인으로 이름 가져오기
                text=row.transcript_text,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                confidence=row.confidence,
                absolute_timestamp=row.start_at or row.created_at,
            )
            utterances.append(utterance)

            # L0 버퍼에 추가
            utterance_with_topic = utterance.model_copy(update={"topic": self.current_topic})
            self.l0_buffer.append(utterance_with_topic)
            self.l0_topic_buffer.append(utterance_with_topic)
            self._speaker_context.add_utterance(utterance_with_topic)

        # 2단계: L1 청크 큐잉 (build_l1=True일 때)
        if build_l1 and utterances:
            self._queue_l1_chunks_from_utterances(utterances)

        logger.info(
            f"Loaded {len(rows)} utterances from DB for meeting {self.meeting_id}, "
            f"L0 buffer size: {len(self.l0_buffer)}, pending L1 chunks: {len(self._pending_l1_chunks)}"
        )
        return len(rows)

    def _queue_l1_chunks_from_utterances(self, utterances: list[Utterance]) -> None:
        """발화 목록을 L1 청크로 분할하여 큐에 추가 (25턴 단위)"""
        if not utterances:
            return

        threshold = self.config.l1_update_turn_threshold

        # 25턴 단위로 청크 분할
        for i in range(0, len(utterances), threshold):
            chunk = utterances[i : i + threshold]
            if chunk:
                self._pending_l1_chunks.append(chunk)

        logger.info(f"Queued {len(self._pending_l1_chunks)} L1 chunks for processing")
