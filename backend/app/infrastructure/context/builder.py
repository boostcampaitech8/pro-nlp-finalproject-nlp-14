"""ContextBuilder - 에이전트 호출 시 컨텍스트 조합

호출 유형에 따라 L0/L1을 적절히 조합하여
OrchestrationState에 주입할 컨텍스트를 생성

호출 유형별 컨텍스트 조합:
- IMMEDIATE_RESPONSE: L0 (최근 발화) + 필요시 L1
- SUMMARY: L1 (토픽 세그먼트) + L0 일부
- ACTION_EXTRACTION: L0 (토픽 전체) + L1
- SEARCH: L1 (맥락) + L0 일부
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.infrastructure.context.manager import ContextManager
from app.infrastructure.context.models import AgentCallType, AgentContext, Participant, TopicSegment
from app.infrastructure.context.runtime import TopicUtteranceCache

if TYPE_CHECKING:
    from app.services.transcript_service import TranscriptService


logger = logging.getLogger(__name__)


class ContextBuilder:
    """에이전트 호출 시 컨텍스트 조합 담당 (Topic-Segmented)

    호출 유형에 따라 필요한 컨텍스트만 선별적으로 주입하여
    토큰 사용량을 최적화
    """

    def build_context(
        self,
        call_type: AgentCallType,
        context_manager: ContextManager,
        user_query: str | None = None,
        participants: list[Participant] | None = None,
    ) -> AgentContext:
        """호출 유형에 맞는 컨텍스트 조합

        Args:
            call_type: 에이전트 호출 유형
            context_manager: 컨텍스트 매니저 인스턴스
            user_query: 사용자 쿼리 (선택)
            participants: 참여자 목록 (선택)

        Returns:
            AgentContext: 조합된 컨텍스트
        """
        match call_type:
            case "IMMEDIATE_RESPONSE":
                return self._build_immediate_context(
                    context_manager, user_query, participants
                )
            case "SUMMARY":
                return self._build_summary_context(context_manager, participants)
            case "ACTION_EXTRACTION":
                return self._build_action_context(context_manager, participants)
            case "SEARCH":
                return self._build_search_context(
                    context_manager, user_query, participants
                )
            case _:
                return self._build_default_context(context_manager, participants)

    def build_planning_input_context(
        self,
        ctx: ContextManager,
        l0_limit: int | None = None,
        user_query: str | None = None,
    ) -> str:
        """Planning 입력용 요약 컨텍스트 (질문 → 토픽 목록 → 최근 발화)

        Args:
            ctx: ContextManager 인스턴스
            l0_limit: L0 발화 최대 개수 (None이면 ctx.context_turns 사용)
            user_query: 사용자 질문 (명확하게 분리하여 표시)

        Returns:
            str: 포맷팅된 컨텍스트
        """
        # l0_limit이 None이면 ContextManager의 모드별 턴 수 사용
        effective_limit = l0_limit if l0_limit is not None else ctx.context_turns

        lines: list[str] = []

        # 1. 사용자 질문 (가장 먼저)
        if user_query:
            lines.append("## 사용자 질문")
            lines.append(f"**\"{user_query}\"**")
            lines.append("")
            lines.append("---")
            lines.append("")

        # 2. 현재 토픽
        lines.append(f"## 현재 토픽: {ctx.current_topic}")
        lines.append("")

        # 3. L1 토픽 목록 (과거 논의)
        lines.append("## L1 토픽 목록 (과거 논의)")
        segments = ctx.get_l1_segments()
        if segments:
            for seg in segments:
                lines.append(f"- {seg.name}")
        else:
            lines.append("- 없음")

        # 4. L0 최근 발화 (회의 맥락)
        lines.append("")
        lines.append("## L0 최근 발화 (회의 맥락)")
        recent = ctx.get_l0_utterances(limit=effective_limit)
        if recent:
            for u in recent:
                ts = u.absolute_timestamp.strftime("%H:%M:%S")
                topic_label = u.topic or ctx.current_topic
                lines.append(f"[{ts}] {u.speaker_name} (topic: {topic_label}): {u.text}")
        else:
            lines.append("- 없음")

        return "\n".join(lines)

    async def build_context_with_search(
        self,
        ctx: ContextManager,
        query: str,
        l0_limit: int | None = None,
        topic_limit: int | None = None,
    ) -> str:
        """시맨틱 서치 기반 컨텍스트 구성 (L0 + 관련 토픽).

        Args:
            ctx: ContextManager 인스턴스
            query: 사용자 쿼리
            l0_limit: L0 발화 최대 개수 (None이면 ctx.context_turns 사용)
            topic_limit: Top-K 토픽 개수 (None이면 config 사용)

        Returns:
            str: 포맷팅된 컨텍스트
        """
        effective_limit = l0_limit if l0_limit is not None else ctx.context_turns

        lines: list[str] = []

        if query:
            lines.append("## 사용자 질문")
            lines.append(f"**\"{query}\"**")
            lines.append("")

        # 비동기 시맨틱 서치 사용
        topic_limit = topic_limit or ctx.config.topic_search_top_k
        topic_results: list[TopicSegment] = await ctx.search_similar_topics_async(
            query, top_k=topic_limit
        )

        lines.append("## 관련 토픽 요약 (Semantic Search)")
        if topic_results:
            for seg in topic_results:
                lines.append(
                    f"- **{seg.name}** "
                    f"(발화 {seg.start_utterance_id}~{seg.end_utterance_id}): {seg.summary}"
                )
        else:
            lines.append("- 없음")

        lines.append("")
        lines.append("## L0 최근 발화 (회의 맥락)")
        recent = ctx.get_l0_utterances(limit=effective_limit)
        if recent:
            for u in recent:
                ts = u.absolute_timestamp.strftime("%H:%M:%S")
                topic_label = u.topic or ctx.current_topic
                lines.append(f"[{ts}] {u.speaker_name} (topic: {topic_label}): {u.text}")
        else:
            lines.append("- 없음")

        return "\n".join(lines)

    def build_required_topic_context(
        self,
        ctx: ContextManager,
        topic_names: list[str],
    ) -> tuple[str, list[str]]:
        """선택된 토픽의 상세 컨텍스트 (L1 내용)"""
        if not topic_names:
            return "", []

        segment_map = {seg.name: seg for seg in ctx.get_l1_segments()}
        missing = [name for name in topic_names if name not in segment_map]

        lines: list[str] = ["## L1 토픽 상세"]
        added = False
        for name in topic_names:
            segment = segment_map.get(name)
            if not segment:
                continue
            added = True
            lines.append(f"### {segment.name}")
            lines.append(segment.summary)
            if segment.key_points:
                lines.append(f"Key Points: {', '.join(segment.key_points)}")
            if segment.key_decisions:
                lines.append(f"Decisions: {', '.join(segment.key_decisions)}")
            if segment.pending_items:
                lines.append(f"Pending: {', '.join(segment.pending_items)}")
            if segment.participants:
                lines.append(f"Participants: {', '.join(segment.participants)}")
            if segment.keywords:
                lines.append(f"Keywords: {', '.join(segment.keywords)}")
            lines.append("")

        if not added:
            return "", missing

        return "\n".join(lines).strip(), missing

    async def build_additional_context_with_search_async(
        self,
        ctx: ContextManager,
        query: str | None,
        top_k: int | None = None,
        threshold: float | None = None,
        meeting_id: str | None = None,
        transcript_service: TranscriptService | None = None,
    ) -> str:
        """비동기 시맨틱 서치 기반 추가 컨텍스트 (L1 토픽 상세).

        2-Step RAG 파이프라인:
        - Step 1: Semantic Search로 관련 토픽 검색 (L1 요약 기반)
        - Step 2: 검색된 토픽의 원문 발화를 DB/메모리에서 조회하여 주입

        Args:
            ctx: ContextManager 인스턴스
            query: 사용자 쿼리
            top_k: Top-K 토픽 개수 (None이면 config 사용)
            threshold: 최소 유사도 임계값 (None이면 config 사용)
            meeting_id: 회의 ID (원문 조회용, None이면 요약본만)
            transcript_service: TranscriptService 인스턴스 (원문 조회용)

        Returns:
            str: L1 토픽 상세 컨텍스트 ([요약 + 원문] 번들)
        """
        if not query:
            return ""

        top_k = top_k or ctx.config.topic_search_top_k
        if threshold is None:
            threshold = ctx.config.topic_search_threshold

        # Step 1: 비동기 시맨틱 서치
        topic_results: list[TopicSegment] = await ctx.search_similar_topics_async(
            query, top_k=top_k, threshold=threshold
        )

        if not topic_results:
            return ""

        # Feature flag 확인
        enable_raw = ctx.config.enable_raw_transcript_injection
        can_fetch_raw = enable_raw and meeting_id and transcript_service

        lines: list[str] = ["## L1 토픽 상세 (Semantic Search)"]

        for segment in topic_results:
            lines.append(f"### {segment.name}")
            lines.append(f"**요약**: {segment.summary}")

            # Metadata
            if segment.key_points:
                lines.append(f"**Key Points**: {', '.join(segment.key_points)}")
            if segment.key_decisions:
                lines.append(f"**Decisions**: {', '.join(segment.key_decisions)}")
            if segment.pending_items:
                lines.append(f"**Pending**: {', '.join(segment.pending_items)}")
            if segment.participants:
                lines.append(f"**Participants**: {', '.join(segment.participants)}")
            if segment.keywords:
                lines.append(f"**Keywords**: {', '.join(segment.keywords)}")

            # Step 2: 원문 주입 (Feature flag + 조건 충족 시)
            if can_fetch_raw:
                raw_utterances = await self._fetch_raw_utterances(
                    ctx,
                    segment,
                    meeting_id,
                    transcript_service,
                )
                if raw_utterances:
                    lines.append("")
                    lines.append("**[원문 대화]**")
                    for utt in raw_utterances:
                        # 시간 포맷팅 (mm:ss)
                        start_sec = utt["start_ms"] // 1000
                        minutes = start_sec // 60
                        seconds = start_sec % 60
                        timestamp = f"{minutes:02d}:{seconds:02d}"

                        lines.append(f"  [{timestamp}] {utt['speaker_name']}: {utt['text']}")

            lines.append("")

        return "\n".join(lines).strip()

    async def _fetch_raw_utterances(
        self,
        ctx: ContextManager,
        segment: TopicSegment,
        meeting_id: str,
        transcript_service: TranscriptService,
    ) -> list[dict]:
        """토픽의 원문 발화 조회 (메모리 → DB fallback)

        Args:
            ctx: ContextManager
            segment: TopicSegment (start/end utterance_id 포함)
            meeting_id: 회의 ID
            transcript_service: TranscriptService

        Returns:
            list[dict]: 원문 발화 리스트 (최대 max_raw_utterances_per_topic개)
        """
        from uuid import UUID

        cache_enabled = bool(ctx.config.enable_utterance_caching)
        topic_cache = TopicUtteranceCache(ttl_seconds=ctx.config.utterance_cache_ttl_seconds)

        # 1. 메모리에서 먼저 시도
        memory_utterances = ctx.get_utterances_in_range(
            segment.start_utterance_id,
            segment.end_utterance_id,
        )

        if memory_utterances:
            # 메모리에서 찾음 → 포맷 변환
            raw_list = [
                {
                    "id": utt.id,
                    "speaker_id": utt.speaker_id,
                    "speaker_name": utt.speaker_name,
                    "text": utt.text,
                    "start_ms": utt.start_ms,
                    "end_ms": utt.end_ms,
                    "confidence": utt.confidence,
                }
                for utt in memory_utterances
            ]

            # 메모리 hit 데이터도 캐시에 반영 (best-effort)
            if cache_enabled:
                await topic_cache.set(meeting_id, segment.id, raw_list)
        else:
            # 2. 메모리에 없음 → 캐시 조회
            raw_list: list[dict] | None = None
            if cache_enabled:
                raw_list = await topic_cache.get(meeting_id, segment.id)

            # 3. 캐시 miss → DB 조회
            if raw_list is None:
                raw_list = []
                # DB에서 조회
                try:
                    raw_list = await transcript_service.get_utterances_by_range(
                        UUID(meeting_id),
                        segment.start_utterance_id,
                        segment.end_utterance_id,
                    )

                    # DB 결과를 캐시에 채움 (write-through)
                    if cache_enabled and raw_list:
                        await topic_cache.set(meeting_id, segment.id, raw_list)
                except Exception as e:
                    # DB 조회 실패 시 빈 리스트 (비치명적)
                    logger.warning(
                        "Failed to fetch raw utterances for segment %s: %s",
                        segment.id,
                        e,
                    )
                    raw_list = []

        # 4. 토큰 제한 적용
        max_utterances = ctx.config.max_raw_utterances_per_topic
        if len(raw_list) > max_utterances:
            raw_list = raw_list[:max_utterances]

        return raw_list

    def build_additional_context_with_search(
        self,
        ctx: ContextManager,
        query: str | None,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> str:
        """시맨틱 서치 기반 추가 컨텍스트 (동기, 하위 호환성).

        Note:
            build_additional_context_with_search_async() 사용 권장

        Args:
            ctx: ContextManager 인스턴스
            query: 사용자 쿼리
            top_k: Top-K 토픽 개수 (None이면 config 사용)
            threshold: 최소 유사도 임계값 (None이면 config 사용)

        Returns:
            str: L1 토픽 상세 컨텍스트
        """
        # 하위 호환성을 위해 기존 동기 인터페이스 유지
        # (현재 코드베이스에서는 async 버전 사용 권장)
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # 이미 이벤트 루프가 실행 중이면 빈 문자열 반환 (비동기 버전 사용 유도)
            logger.warning(
                "build_additional_context_with_search called in running event loop; "
                "use build_additional_context_with_search_async instead"
            )
            _ = loop  # unused variable 방지
            return ""
        except RuntimeError:
            return asyncio.run(
                self.build_additional_context_with_search_async(
                    ctx,
                    query,
                    top_k=top_k,
                    threshold=threshold,
                )
            )

    def _build_immediate_context(
        self,
        ctx: ContextManager,
        user_query: str | None,
        participants: list[Participant] | None,
    ) -> AgentContext:
        """즉시 응답용 컨텍스트 (L0 중심)

        팩트체크, 즉시 질문 응답 등에 사용
        """
        # 화자 역할 추론
        speaker_roles = ctx.speaker_context.infer_roles()

        return AgentContext(
            meeting_id=ctx.meeting_id,
            current_time=datetime.now(timezone.utc),
            call_type="IMMEDIATE_RESPONSE",
            recent_utterances=ctx.get_l0_utterances(limit=10),
            current_topic=ctx.current_topic,
            topic_segments=None,  # 즉시 응답에는 L1 불필요
            participants=participants or [],
            speaker_roles=speaker_roles,
        )

    def _build_summary_context(
        self,
        ctx: ContextManager,
        participants: list[Participant] | None,
    ) -> AgentContext:
        """요약용 컨텍스트 (L1 중심)

        회의 요약 요청 시 사용
        """
        # 모든 토픽 세그먼트의 pending items 수집
        pending_items: list[str] = []
        for segment in ctx.l1_segments:
            pending_items.extend(segment.pending_items)

        return AgentContext(
            meeting_id=ctx.meeting_id,
            current_time=datetime.now(timezone.utc),
            call_type="SUMMARY",
            recent_utterances=ctx.get_l0_utterances(limit=5),  # 최근 발화만 보완
            current_topic=ctx.current_topic,
            topic_segments=ctx.get_l1_segments(),
            pending_items=pending_items,
            participants=participants or [],
            speaker_roles=ctx.speaker_context.infer_roles(),
        )

    def _build_action_context(
        self,
        ctx: ContextManager,
        participants: list[Participant] | None,
    ) -> AgentContext:
        """액션아이템 추출용 컨텍스트 (L0 + L1)

        현재 토픽의 전체 발화 + 과거 토픽 요약
        """
        return AgentContext(
            meeting_id=ctx.meeting_id,
            current_time=datetime.now(timezone.utc),
            call_type="ACTION_EXTRACTION",
            recent_utterances=ctx.get_topic_utterances(),  # 토픽 전체 발화
            current_topic=ctx.current_topic,
            topic_segments=ctx.get_l1_segments(),
            participants=participants or [],
            speaker_roles=ctx.speaker_context.infer_roles(),
        )

    def _build_search_context(
        self,
        ctx: ContextManager,
        user_query: str | None,
        participants: list[Participant] | None,
    ) -> AgentContext:
        """검색용 컨텍스트 (L1 + 맥락)

        mit_search: 문서/과거 회의 검색
        """
        return AgentContext(
            meeting_id=ctx.meeting_id,
            current_time=datetime.now(timezone.utc),
            call_type="SEARCH",
            recent_utterances=ctx.get_l0_utterances(limit=5),  # 맥락 파악용
            current_topic=ctx.current_topic,
            topic_segments=ctx.get_l1_segments(),
            participants=participants or [],
            speaker_roles=ctx.speaker_context.infer_roles(),
        )

    def _build_default_context(
        self,
        ctx: ContextManager,
        participants: list[Participant] | None,
    ) -> AgentContext:
        """기본 컨텍스트 (전체 제공)"""
        pending_items: list[str] = []
        for segment in ctx.l1_segments:
            pending_items.extend(segment.pending_items)

        return AgentContext(
            meeting_id=ctx.meeting_id,
            current_time=datetime.now(timezone.utc),
            call_type="default",
            recent_utterances=ctx.get_l0_utterances(),
            current_topic=ctx.current_topic,
            topic_segments=ctx.get_l1_segments(),
            pending_items=pending_items,
            participants=participants or [],
            speaker_roles=ctx.speaker_context.infer_roles(),
        )


def format_context_as_system_prompt(ctx: AgentContext) -> str:
    """AgentContext를 시스템 프롬프트로 변환

    에이전트 호출 시 context를 시스템 메시지로 주입

    Args:
        ctx: 에이전트 컨텍스트

    Returns:
        str: 포맷팅된 시스템 프롬프트
    """
    parts = [
        "## 현재 회의 정보",
        f"- 회의 ID: {ctx.meeting_id}",
        f"- 현재 시각: {ctx.current_time.isoformat()}",
        f"- 호출 유형: {ctx.call_type}",
        f"- 현재 토픽: {ctx.current_topic or '미정'}",
        "",
    ]

    # 참여자 정보
    if ctx.participants:
        parts.append("## 참여자")
        for p in ctx.participants:
            role = ctx.speaker_roles.get(p.user_id, "")
            role_str = f" ({role})" if role else ""
            parts.append(f"- {p.name}{role_str}")
        parts.append("")

    # L0: 최근 발화
    if ctx.recent_utterances:
        parts.append("## 최근 발화 (L0)")
        for u in ctx.recent_utterances:
            ts = u.absolute_timestamp.strftime("%H:%M:%S")
            parts.append(f"[{ts}] {u.speaker_name}: {u.text}")
        parts.append("")

    # L1: 토픽 세그먼트
    if ctx.topic_segments:
        parts.append("## 토픽별 요약 (L1)")
        for segment in ctx.topic_segments:
            parts.append(f"### {segment.name}")
            parts.append(segment.summary)
            if segment.key_decisions:
                parts.append("결정사항:")
                for decision in segment.key_decisions:
                    parts.append(f"  - {decision}")
            if segment.keywords:
                parts.append(f"키워드: {', '.join(segment.keywords)}")
            parts.append("")

    # L1: 미해결 사항
    if ctx.pending_items:
        parts.append("## 미해결 사항")
        for item in ctx.pending_items:
            parts.append(f"- {item}")
        parts.append("")

    return "\n".join(parts)
