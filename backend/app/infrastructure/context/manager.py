"""ContextManager - 실시간 회의 컨텍스트 관리자

책임:
1. STT 세그먼트 수신 및 L0 업데이트
2. 토픽 전환 감지 및 L1 업데이트 트리거
3. 에이전트 호출 시 적절한 컨텍스트 조합 제공

상태 관리:
- DB(PostgreSQL)가 SSOT, 인메모리는 캐시
- 워커 시작 시 DB에서 기존 상태 복원
- 주기적으로 DB에 상태 저장
"""

import json
import logging
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

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
    """실시간 회의 컨텍스트 관리자 (Topic-Segmented)

    책임:
    1. STT 수신 및 L0(현재 토픽) 버퍼링
    2. 주기적(N턴)으로 토픽 변경 감지
    3. 토픽 변경 시: 현재 버퍼 요약 -> L1(TopicSegment) 저장 -> 버퍼 초기화

    상태 영속화:
    - 워커 재시작/스케일아웃 대응을 위해 DB에 상태 저장
    - 인메모리는 성능을 위한 캐시로만 사용
    """

    def __init__(self, meeting_id: str, config: ContextConfig | None = None):
        self.meeting_id = meeting_id
        self.config = config or ContextConfig()
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

        # DB 동기화 추적
        self._utterances_since_db_sync: int = 0
        self._last_db_sync: datetime = datetime.now(timezone.utc)

        # 토픽 감지기
        self._topic_detector = TopicDetector(config=self.config)

        # 화자 컨텍스트 관리
        self._speaker_context = SpeakerContext(
            max_buffer_per_speaker=self.config.speaker_buffer_max_per_speaker
        )

    async def add_utterance(self, utterance: Utterance) -> None:
        """새 발화 추가

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

        # L1 업데이트 필요 여부 확인
        should_update, reason, next_topic = await self._should_update_l1(
            utterance_with_topic
        )
        if should_update:
            await self._update_l1(reason, next_topic)

        # DB 동기화 체크
        await self._maybe_sync_to_db()

        logger.debug(
            f"Utterance added: {utterance.speaker_name}: {utterance.text[:50]}..."
        )

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

        # DB에 L1 상태 저장
        await self._sync_to_db()

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
            id=str(uuid.uuid4()),
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
            from app.infrastructure.graph.integration.llm import llm
        except Exception as e:
            logger.debug(f"Failed to import LLM client: {e}")
            return None

        try:
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

    # === DB 동기화 메서드 ===

    async def _sync_to_db(self) -> None:
        """현재 상태를 DB에 저장

        워커 재시작/스케일아웃 대응을 위해 주기적으로 호출
        """
        try:
            # TODO: 실제 DB 모델 및 저장 로직 구현
            # MeetingContextState 테이블에 저장
            # - current_topic
            # - l1_segments (JSON)
            # - _last_summarized_utterance_id
            # - _last_l1_update
            logger.debug(f"Syncing context to DB: meeting={self.meeting_id}")
            self._last_db_sync = datetime.now(timezone.utc)
            self._utterances_since_db_sync = 0
        except Exception as e:
            logger.error(f"Failed to sync context to DB: {e}")

    async def restore_from_db(self) -> bool:
        """DB에서 기존 상태 복원

        워커 시작 시 호출하여 기존 회의 컨텍스트 복원

        Returns:
            bool: 복원 성공 여부
        """
        try:
            # TODO: 실제 DB 조회 및 상태 복원 로직 구현
            # 1. MeetingContextState 테이블에서 조회
            # 2. 인메모리 상태에 복원
            # 3. 최근 N개 발화 DB에서 로드하여 l0_buffer 채우기
            logger.info(f"Restoring context from DB: meeting={self.meeting_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore context from DB: {e}")
            return False

    async def _maybe_sync_to_db(self) -> None:
        """조건 충족 시 DB 동기화

        - 발화 N개마다
        - 또는 시간 간격마다
        """
        self._utterances_since_db_sync += 1

        should_sync = (
            self._utterances_since_db_sync >= self.config.db_sync_utterance_threshold
            or (datetime.now(timezone.utc) - self._last_db_sync).total_seconds()
            >= self.config.db_sync_interval_seconds
        )

        if should_sync:
            await self._sync_to_db()

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
