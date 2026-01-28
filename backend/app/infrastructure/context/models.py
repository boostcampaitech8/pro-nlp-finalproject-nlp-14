"""Context Engineering Data Models"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Utterance(BaseModel):
    """표준화된 발화 모델 (L0)"""

    id: int
    speaker_id: str
    speaker_name: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    absolute_timestamp: datetime

    # 추가 메타데이터
    topic: str | None = None  # 토픽 할당 결과
    topic_id: str | None = None  # 토픽 세그먼트 ID

    model_config = ConfigDict(frozen=True)  # 불변 객체


class TopicSegment(BaseModel):
    """토픽 세그먼트 (L1)"""

    id: str
    name: str  # 토픽 제목
    summary: str  # 요약 내용
    start_utterance_id: int
    end_utterance_id: int
    key_points: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    key_decisions: list[str] = Field(default_factory=list)  # 간단한 텍스트로 저장
    pending_items: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)


class Participant(BaseModel):
    """참여자 정보"""

    user_id: str
    name: str
    role: str | None = None


AgentCallType = Literal[
    "IMMEDIATE_RESPONSE",
    "SUMMARY",
    "ACTION_EXTRACTION",
    "SEARCH",
]


class AgentContext(BaseModel):
    """에이전트에 주입되는 통합 컨텍스트"""

    # 메타 정보
    meeting_id: str
    current_time: datetime
    call_type: str  # AgentCallType string representation

    # L0 컨텍스트 (선택적)
    recent_utterances: list[Utterance] | None = None
    current_topic: str | None = None

    # L1 컨텍스트 (선택적)
    # 기존 string map 구조에서 TopicSegment 리스트로 변경
    topic_segments: list[TopicSegment] | None = None

    # 하위 호환성 및 빠른 참조를 위한 필드 유지
    pending_items: list[str] | None = None

    # 참여자 정보
    participants: list[Participant] = Field(default_factory=list)
    speaker_roles: dict[str, str] = Field(default_factory=dict)
