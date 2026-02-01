"""ContextBuilder - 에이전트 호출 시 컨텍스트 조합

호출 유형에 따라 L0/L1을 적절히 조합하여
OrchestrationState에 주입할 컨텍스트를 생성

호출 유형별 컨텍스트 조합:
- IMMEDIATE_RESPONSE: L0 (최근 발화) + 필요시 L1
- SUMMARY: L1 (토픽 세그먼트) + L0 일부
- ACTION_EXTRACTION: L0 (토픽 전체) + L1
- SEARCH: L1 (맥락) + L0 일부
"""

from datetime import datetime, timezone

from app.infrastructure.context.manager import ContextManager
from app.infrastructure.context.models import AgentCallType, AgentContext, Participant


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
        l0_limit: int = 10,
        user_query: str | None = None,
    ) -> str:
        """Planning 입력용 요약 컨텍스트 (질문 → 토픽 목록 → 최근 발화)

        Args:
            ctx: ContextManager 인스턴스
            l0_limit: L0 발화 최대 개수
            user_query: 사용자 질문 (명확하게 분리하여 표시)

        Returns:
            str: 포맷팅된 컨텍스트
        """
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
                summary_preview = seg.summary[:100] + "..." if len(seg.summary) > 100 else seg.summary
                lines.append(
                    f"- **{seg.name}** (발화 {seg.start_utterance_id}~{seg.end_utterance_id}): {summary_preview}"
                )
        else:
            lines.append("- 없음")

        # 4. L0 최근 발화 (회의 맥락)
        lines.append("")
        lines.append("## L0 최근 발화 (회의 맥락)")
        recent = ctx.get_l0_utterances(limit=l0_limit)
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
