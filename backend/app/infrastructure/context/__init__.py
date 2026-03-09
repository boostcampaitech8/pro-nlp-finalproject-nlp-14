"""Context Engineering Module

실시간 회의 컨텍스트 관리를 위한 모듈.

계층적 메모리 시스템:
- L0 (Raw Window): 최근 N턴 발화 원본
- L1 (Running Summary): 토픽별 요약 (Topic-Segmented)

사용 예시:
    from app.infrastructure.context import ContextManager, ContextBuilder

    # 회의 시작 시 ContextManager 생성
    ctx_manager = ContextManager(meeting_id="meeting-xxx")

    # 기존 상태 복원 (워커 재시작 대응)
    await ctx_manager.load_from_db()

    # STT 세그먼트 수신 시
    await ctx_manager.add_utterance(utterance)

    # 에이전트 호출 시
    builder = ContextBuilder()
    context = builder.build_context(
        call_type="IMMEDIATE_RESPONSE",
        context_manager=ctx_manager,
    )

    # 시스템 프롬프트로 변환
    prompt = format_context_as_system_prompt(context)
"""

from app.infrastructure.context.builder import ContextBuilder, format_context_as_system_prompt
from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.manager import ContextManager
from app.infrastructure.context.models import (
    AgentCallType,
    AgentContext,
    Participant,
    TopicSegment,
    TopicSummary,
    Utterance,
)
from app.infrastructure.context.speaker_context import SpeakerContext, SpeakerStats

__all__ = [
    # Config
    "ContextConfig",
    # Core
    "ContextManager",
    "ContextBuilder",
    "format_context_as_system_prompt",
    # Detectors
    "SpeakerContext",
    "SpeakerStats",
    # Models
    "AgentCallType",
    "AgentContext",
    "Utterance",
    "TopicSegment",
    "TopicSummary",
    "Participant",
]
