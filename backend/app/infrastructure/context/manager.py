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
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.models import TopicSegment, Utterance
from app.infrastructure.context.prompts.summarization import (
    L1_SUMMARY_PROMPT,
    RECURSIVE_SUMMARY_PROMPT,
)
from app.infrastructure.context.speaker_context import SpeakerContext
from app.infrastructure.context.topic_detector import TopicDetector

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

        # L0: Raw Window (고정 크기)
        self.l0_buffer: deque[Utterance] = deque(maxlen=self.config.l0_max_turns)
        self.current_topic: str = "Intro"  # 초기 토픽

        # L0: Topic Buffer (현재 토픽 발화, 제한 있음 - 무한 증식 방지)
        self.l0_topic_buffer: deque[Utterance] = deque(
            maxlen=self.config.l0_topic_buffer_max_turns
        )

        # L1: Topic Segments
        self.l1_segments: list[TopicSegment] = []

        # 업데이트 추적 (UTC 사용)
        self._last_l1_update: datetime = datetime.now(timezone.utc)
        self._turn_count_since_l1: int = 0

        # 반복 요약 방지: 마지막으로 요약에 포함된 발화 ID
        self._last_summarized_utterance_id: int | None = None

        # 토픽 감지기
        self._topic_detector = TopicDetector(config=self.config)

        # 화자 컨텍스트 관리
        self._speaker_context = SpeakerContext(
            max_buffer_per_speaker=self.config.speaker_buffer_max_per_speaker
        )

        # L1 비동기 처리용
        self._pending_l1_chunks: list[list[Utterance]] = []  # 요약 대기 청크
        self._l1_task: asyncio.Task | None = None  # 백그라운드 L1 처리 태스크
        self._l1_processing: bool = False  # L1 처리 중 플래그

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
        self._turn_count_since_l1 += 1

        # 화자 컨텍스트 업데이트
        self._speaker_context.add_utterance(utterance_with_topic)

        # L1 업데이트 필요 여부 확인 (토픽 전환 키워드 또는 임계값)
        should_queue = self._should_queue_l1(utterance_with_topic)
        if should_queue:
            # 현재 토픽 버퍼를 청크로 저장하고 비동기 처리 시작
            self._queue_l1_chunk()

        logger.debug(
            f"Utterance added: {utterance.speaker_name}: {utterance.text[:50]}..."
        )

    def _should_queue_l1(self, utterance: Utterance) -> bool:
        """L1 청크 큐잉 필요 여부 판단 (동기, 빠른 체크)"""
        # 요약할 새 발화가 있는지 확인
        new_utterances = self._get_unsummarized_utterances()
        if not new_utterances:
            return False

        # 토픽 전환 키워드 감지
        if self._topic_detector.quick_check(utterance.text):
            return True

        # 턴 수 임계값 도달
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
        self._turn_count_since_l1 = 0

        logger.info(
            f"L1 chunk queued: {len(utterances_to_queue)} utterances, "
            f"total pending: {len(self._pending_l1_chunks)}"
        )

    async def await_pending_l1(self) -> None:
        """대기 중인 모든 L1 처리 완료 대기 (에이전트 호출 전 사용)

        에이전트 호출 전에 이 메서드를 호출하여 모든 L1 요약이
        완료된 상태에서 컨텍스트를 제공합니다.
        """
        if not self._pending_l1_chunks:
            logger.debug("No pending L1 chunks to process")
            return

        logger.info(f"Awaiting {len(self._pending_l1_chunks)} pending L1 chunks...")

        # 모든 대기 청크를 병렬로 처리
        chunks = self._pending_l1_chunks.copy()
        self._pending_l1_chunks.clear()

        # 비동기 병렬 요약 생성
        async def summarize_chunk(
            chunk: list[Utterance], chunk_idx: int
        ) -> tuple[int, dict]:
            topic_name = f"Topic_{len(self.l1_segments) + chunk_idx + 1}"
            if len(self.l1_segments) == 0 and chunk_idx == 0:
                topic_name = "Intro"
            summary_payload = await self._summarize_topic(chunk, topic_name)
            return chunk_idx, summary_payload

        tasks = [summarize_chunk(chunk, i) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)

        # 결과를 순서대로 L1 세그먼트에 추가
        for chunk_idx, summary_payload in sorted(results, key=lambda x: x[0]):
            chunk = chunks[chunk_idx]
            topic_name = f"Topic_{len(self.l1_segments) + 1}"
            if len(self.l1_segments) == 0:
                topic_name = "Intro"

            segment = self._build_topic_segment(
                topic_name=summary_payload.get("detected_topic") or topic_name,
                summary_payload=summary_payload,
                utterances=chunk,
            )
            self.l1_segments.append(segment)

        # 현재 토픽 업데이트
        if self.l1_segments:
            self.current_topic = self.l1_segments[-1].name

        logger.info(f"L1 processing complete: {len(self.l1_segments)} total segments")

    @property
    def has_pending_l1(self) -> bool:
        """대기 중인 L1 처리가 있는지 확인"""
        return len(self._pending_l1_chunks) > 0

    async def _should_update_l1(
        self,
        latest_utterance: Utterance,
    ) -> tuple[bool, str, str | None]:
        """L1 업데이트 필요 여부 판단

        주의:
        - 요약할 새 발화가 있는지 먼저 확인 (반복 요약 방지)
        - 키워드 기반 빠른 체크 또는 N턴마다 LLM 정밀 감지
        """
        # 요약할 새 발화가 있는지 먼저 확인
        new_utterances = self._get_unsummarized_utterances()
        if not new_utterances:
            return False, "", None

        # 1. 토픽 전환 감지 (키워드 기반 빠른 검사 또는 N턴 주기 체크)
        should_check_topic = False
        if self.config.topic_quick_check_enabled:
            if self._topic_detector.quick_check(latest_utterance.text):
                should_check_topic = True

        interval = self.config.l1_topic_check_interval_turns
        if interval > 0 and self._turn_count_since_l1 % interval == 0:
            should_check_topic = True

        if should_check_topic:
            result = await self._topic_detector.detect(
                recent_utterances=list(self.l0_buffer)[-5:],
                previous_topic_summary=self._get_current_topic_summary(),
            )
            if result.topic_changed:
                next_topic = result.current_topic or self._generate_next_topic_name()
                return True, "topic_change", next_topic

        # 2. 턴 수 기반 (새 발화 기준)
        if len(new_utterances) >= self.config.l1_update_turn_threshold:
            return True, "turn_limit", None

        # 3. 시간 기반 (UTC 사용, 최소 발화 수 조건)
        elapsed = datetime.now(timezone.utc) - self._last_l1_update
        min_utterances = self.config.l1_min_new_utterances_for_time_trigger
        if (
            elapsed > timedelta(minutes=self.config.l1_update_interval_minutes)
            and len(new_utterances) >= min_utterances
        ):
            return True, "time_limit", None

        return False, "", None

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

    async def _update_l1(self, reason: str, next_topic: str | None = None) -> None:
        """L1 업데이트 수행

        주의:
        - 요약 후 _last_summarized_utterance_id 업데이트 필수
        - topic_change 시에만 토픽 버퍼 초기화
        - 시간/턴 트리거 시에는 버퍼 유지 (토픽 연속성)
        """
        # 요약할 발화 목록
        utterances_to_summarize = self._get_unsummarized_utterances()
        if not utterances_to_summarize:
            return

        logger.info(
            f"L1 update triggered: reason={reason}, "
            f"new_utterances={len(utterances_to_summarize)}"
        )

        current_topic_name = self.current_topic
        existing_segment = self._find_current_topic_segment()

        if existing_segment:
            summary_payload = await self._recursive_summarize(
                previous_summary=existing_segment.summary,
                new_utterances=utterances_to_summarize,
            )
            self._apply_recursive_summary(
                existing_segment,
                summary_payload,
                utterances_to_summarize,
            )
        else:
            summary_payload = await self._summarize_topic(
                utterances=utterances_to_summarize,
                topic_name=current_topic_name,
            )
            segment = self._build_topic_segment(
                topic_name=current_topic_name,
                summary_payload=summary_payload,
                utterances=utterances_to_summarize,
            )
            self.l1_segments.append(segment)

        # 반복 요약 방지: 마지막 발화 ID 기록
        if utterances_to_summarize:
            self._last_summarized_utterance_id = utterances_to_summarize[-1].id

        # 토픽 버퍼 초기화 (토픽 전환 시에만)
        if reason in ("topic_change", "manual_topic_change"):
            self.l0_topic_buffer.clear()
            self._last_summarized_utterance_id = None  # 새 토픽 시작
            # 다음 토픽 이름 설정
            self.current_topic = next_topic or self._generate_next_topic_name()

        # 업데이트 추적 리셋 (UTC 사용)
        self._last_l1_update = datetime.now(timezone.utc)
        self._turn_count_since_l1 = 0

    def _get_current_topic_summary(self) -> str:
        """현재 토픽 요약 반환"""
        for segment in reversed(self.l1_segments):
            if segment.name == self.current_topic:
                return segment.summary
        return ""

    def _find_current_topic_segment(self) -> TopicSegment | None:
        """현재 토픽에 해당하는 마지막 세그먼트 반환"""
        for segment in reversed(self.l1_segments):
            if segment.name == self.current_topic:
                return segment
        return None

    def _generate_next_topic_name(self) -> str:
        """다음 토픽 이름 생성"""
        return f"Topic_{len(self.l1_segments) + 1}"

    def _format_utterances(self, utterances: list[Utterance]) -> str:
        """발화를 프롬프트 입력용 문자열로 포맷팅"""
        lines: list[str] = []
        for u in utterances:
            if self.config.l0_include_timestamps:
                ts = u.absolute_timestamp.strftime("%H:%M:%S")
                lines.append(f"[{ts}] {u.speaker_name}: {u.text}")
            else:
                lines.append(f"[{u.speaker_name}] {u.text}")
        return "\n".join(lines)

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

    @staticmethod
    def _normalize_list(value: object) -> list[str]:
        """LLM 응답 값 정규화 (list[str])"""
        if not value:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if v]
        if isinstance(value, str):
            return [value]
        return [str(value)]

    @staticmethod
    def _merge_unique(existing: list[str], new_items: list[str]) -> list[str]:
        """중복 없이 리스트 병합 (순서 유지)"""
        seen: set[str] = set()
        merged: list[str] = []
        for item in existing + new_items:
            if not item:
                continue
            if item not in seen:
                seen.add(item)
                merged.append(item)
        return merged

    async def _summarize_topic(
        self,
        utterances: list[Utterance],
        topic_name: str,
    ) -> dict:
        """토픽 요약 생성 (LLM 우선, 실패 시 fallback)"""
        utterances_text = self._format_utterances(utterances)
        prompt = L1_SUMMARY_PROMPT.format(
            topic_name=topic_name,
            topic_utterances=utterances_text,
        )

        llm_response = await self._call_llm(
            prompt,
            max_tokens=self.config.l1_summary_max_tokens,
        )
        if llm_response:
            data = self._safe_json_loads(llm_response)
            if data and data.get("summary"):
                participants = self._normalize_list(data.get("participants"))
                if not participants:
                    participants = self._collect_participants(utterances)

                return {
                    "summary": str(data.get("summary", "")).strip(),
                    "key_points": self._normalize_list(data.get("key_points")),
                    "decisions": self._normalize_list(data.get("decisions")),
                    "pending": self._normalize_list(data.get("pending")),
                    "participants": participants,
                    "keywords": self._normalize_list(data.get("keywords")),
                }

        # fallback summary
        fallback_summary = self._fallback_summary(topic_name, utterances)
        return {
            "summary": fallback_summary,
            "key_points": [],
            "decisions": [],
            "pending": [],
            "participants": self._collect_participants(utterances),
            "keywords": [],
        }

    async def _recursive_summarize(
        self,
        previous_summary: str,
        new_utterances: list[Utterance],
    ) -> dict:
        """재귀적 요약 (기존 요약 + 새 발화)"""
        utterances_text = self._format_utterances(new_utterances)
        prompt = RECURSIVE_SUMMARY_PROMPT.format(
            previous_summary=previous_summary or "(empty)",
            start_turn=new_utterances[0].id,
            end_turn=new_utterances[-1].id,
            new_utterances=utterances_text,
        )

        llm_response = await self._call_llm(
            prompt,
            max_tokens=self.config.l1_summary_max_tokens,
        )
        if llm_response:
            data = self._safe_json_loads(llm_response)
            if data and data.get("summary"):
                return {
                    "summary": str(data.get("summary", "")).strip(),
                    "key_points": self._normalize_list(data.get("key_points")),
                    "keywords": self._normalize_list(data.get("keywords")),
                }

        # fallback: previous summary + last utterance snippet
        last_text = new_utterances[-1].text if new_utterances else ""
        fallback_summary = f"{previous_summary}\n업데이트: {last_text[:120]}".strip()
        return {
            "summary": fallback_summary,
            "key_points": [],
            "keywords": [],
        }

    def _build_topic_segment(
        self,
        topic_name: str,
        summary_payload: dict,
        utterances: list[Utterance],
    ) -> TopicSegment:
        """TopicSegment 생성"""
        return TopicSegment(
            id=str(uuid_module.uuid4()),
            name=topic_name,
            summary=summary_payload.get("summary", ""),
            start_utterance_id=utterances[0].id,
            end_utterance_id=utterances[-1].id,
            key_points=summary_payload.get("key_points", []),
            keywords=summary_payload.get("keywords", []),
            key_decisions=summary_payload.get("decisions", []),
            pending_items=summary_payload.get("pending", []),
            participants=summary_payload.get("participants", []),
        )

    def _apply_recursive_summary(
        self,
        segment: TopicSegment,
        summary_payload: dict,
        utterances: list[Utterance],
    ) -> None:
        """기존 세그먼트에 재귀 요약 결과 반영"""
        if summary_payload.get("summary"):
            segment.summary = summary_payload["summary"]

        if summary_payload.get("key_points"):
            segment.key_points = summary_payload["key_points"]

        segment.end_utterance_id = utterances[-1].id
        segment.keywords = self._merge_unique(
            segment.keywords, summary_payload.get("keywords", [])
        )
        segment.participants = self._merge_unique(
            segment.participants, self._collect_participants(utterances)
        )

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

    async def _call_llm(self, prompt: str, max_tokens: int | None = None) -> str | None:
        """LLM 호출 (실패 시 None 반환)"""
        if not self._llm_enabled:
            return None

        try:
            from app.infrastructure.graph.integration.llm import get_base_llm
        except Exception as e:
            logger.debug(f"Failed to import LLM client: {e}")
            return None

        try:
            llm = get_base_llm()
            runnable = llm.bind(max_tokens=max_tokens) if max_tokens else llm
            response = await runnable.ainvoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning(f"Context summarization LLM call failed: {e}")
            return None

    @staticmethod
    def _safe_json_loads(text: str) -> dict | None:
        """LLM 응답에서 JSON 파싱 (부분 추출 지원)"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
        return None

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
            "last_l1_update": self._last_l1_update.isoformat(),
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
    def topic_detector(self) -> TopicDetector:
        """토픽 감지기 접근"""
        return self._topic_detector

    # === 토픽 수동 제어 ===

    async def force_topic_change(self, new_topic_name: str) -> None:
        """수동 토픽 전환

        Args:
            new_topic_name: 새 토픽 이름
        """
        if self.l0_topic_buffer:
            await self._update_l1("manual_topic_change", new_topic_name)
        else:
            self.current_topic = new_topic_name
        logger.info(f"Manual topic change to: {new_topic_name}")

    def add_topic_keywords(self, keywords: list[str]) -> None:
        """토픽 감지 키워드 추가

        Args:
            keywords: 추가할 키워드 목록
        """
        self._topic_detector.add_custom_keywords(keywords)

    # === DB 로드 메서드 ===

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

        from app.models.transcript_ import Transcript

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
        """발화 목록을 L1 청크로 분할하여 큐에 추가"""
        if not utterances:
            return

        # 토픽 전환 키워드로 청크 분할
        current_chunk: list[Utterance] = []
        threshold = self.config.l1_update_turn_threshold

        for utt in utterances:
            current_chunk.append(utt)

            # 토픽 전환 키워드 감지 또는 임계값 도달 시 청크 분할
            is_topic_change = self._topic_detector.quick_check(utt.text)
            if is_topic_change or len(current_chunk) >= threshold:
                self._pending_l1_chunks.append(current_chunk)
                current_chunk = []

        # 남은 발화 처리
        if current_chunk:
            self._pending_l1_chunks.append(current_chunk)

        logger.info(f"Queued {len(self._pending_l1_chunks)} L1 chunks for processing")

    async def _build_l1_batch(self, utterances: list[Utterance]) -> None:
        """L1 세그먼트 배치 생성 (비동기 병렬 처리)

        발화를 토픽 키워드 기준으로 청크로 나누고,
        각 청크의 요약을 병렬로 생성합니다.
        """
        import asyncio

        if not utterances:
            return

        # 토픽 전환 키워드로 청크 분할
        chunks: list[list[Utterance]] = []
        current_chunk: list[Utterance] = []
        threshold = self.config.l1_update_turn_threshold

        for utt in utterances:
            current_chunk.append(utt)

            # 토픽 전환 키워드 감지 또는 임계값 도달 시 청크 분할
            is_topic_change = self._topic_detector.quick_check(utt.text)
            if is_topic_change or len(current_chunk) >= threshold:
                chunks.append(current_chunk)
                current_chunk = []

        # 남은 발화 처리
        if current_chunk:
            chunks.append(current_chunk)

        if not chunks:
            return

        logger.info(f"L1 배치 요약 시작: {len(chunks)}개 청크")

        # 비동기 병렬 요약 생성
        async def summarize_chunk(
            chunk: list[Utterance], chunk_idx: int
        ) -> tuple[int, dict]:
            topic_name = f"Topic_{chunk_idx + 1}" if chunk_idx > 0 else "Intro"
            summary_payload = await self._summarize_topic(chunk, topic_name)
            return chunk_idx, summary_payload

        tasks = [summarize_chunk(chunk, i) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)

        # 결과를 순서대로 L1 세그먼트에 추가
        for chunk_idx, summary_payload in sorted(results, key=lambda x: x[0]):
            chunk = chunks[chunk_idx]
            topic_name = f"Topic_{chunk_idx + 1}" if chunk_idx > 0 else "Intro"

            segment = self._build_topic_segment(
                topic_name=summary_payload.get("detected_topic") or topic_name,
                summary_payload=summary_payload,
                utterances=chunk,
            )
            self.l1_segments.append(segment)

        # 현재 토픽 업데이트
        if self.l1_segments:
            self.current_topic = self.l1_segments[-1].name

        logger.info(f"L1 배치 요약 완료: {len(self.l1_segments)}개 세그먼트 생성")
