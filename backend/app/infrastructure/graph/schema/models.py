"""공통 Pydantic 모델 정의"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    """라우팅 결정"""

    next: str = Field(..., description="다음 노드명")
    reason: str = Field(..., description="라우팅 사유")


class PlanningOutput(BaseModel):
    """플래닝 출력"""

    steps: list[str] = Field(default_factory=list, description="실행 단계 목록")
    requires_summary: bool = Field(False, description="요약 필요 여부")
    requires_search: bool = Field(False, description="검색 필요 여부")
    filter_params: dict[str, Any] = Field(
        default_factory=dict, description="필터링 파라미터"
    )


class Utterance(BaseModel):
    """발화 단위"""

    speaker_id: str = Field(..., description="화자 ID")
    speaker_name: str = Field(..., description="화자 이름")
    text: str = Field(..., description="발화 텍스트")
    start_time: float = Field(..., description="시작 시각 (초)")
    end_time: float = Field(..., description="종료 시각 (초)")
    timestamp: datetime | None = Field(None, description="wall-clock 타임스탬프")


class GTDecision(BaseModel):
    """GT에서 조회한 결정사항"""

    id: UUID = Field(..., description="결정 ID")
    agenda_id: UUID = Field(..., description="안건 ID")
    agenda_topic: str = Field(..., description="안건 주제")
    content: str = Field(..., description="결정 내용")
    context: str | None = Field(None, description="결정 맥락")
    created_at: datetime = Field(..., description="생성 시각")


class Contradiction(BaseModel):
    """모순 감지 결과"""

    utterance_text: str = Field(..., description="모순되는 발화")
    gt_decision: GTDecision = Field(..., description="모순되는 GT 결정")
    reason: str = Field(..., description="모순 이유 설명")
    severity: str = Field("medium", description="심각도 (low/medium/high)")


class SummaryOutput(BaseModel):
    """요약 출력 결과"""

    overall: str = Field(..., description="전체 요약")
    key_points: list[str] = Field(default_factory=list, description="핵심 포인트")
    topics: list[dict[str, str]] = Field(
        default_factory=list, description="토픽별 요약 [{'topic': ..., 'summary': ...}]"
    )
    decisions_mentioned: list[str] = Field(
        default_factory=list, description="언급된 결정사항"
    )
    contradictions: list[Contradiction] = Field(
        default_factory=list, description="감지된 모순"
    )
    summary_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="메타데이터 (duration, speaker_count, timerange 등)",
    )


class ErrorRecord(BaseModel):
    """에러 기록"""

    node: str = Field(..., description="에러 발생 노드")
    error_type: str = Field(..., description="에러 타입")
    message: str = Field(..., description="에러 메시지")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
