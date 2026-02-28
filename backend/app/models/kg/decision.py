"""KG Decision 엔티티"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Decision 상태 정의
# - draft: 리뷰 대기 중 (AI 생성 또는 Suggestion에서 생성)
# - latest: 전원 승인 완료 (GT, Ground Truth)
# - outdated: latest였다가 다른 회의에서 새 latest로 대체됨
# - superseded: draft였다가 Suggestion 수락으로 새 draft로 대체됨
# - rejected: 거절됨
DecisionStatus = Literal["draft", "latest", "outdated", "superseded", "rejected"]


class KGDecision(BaseModel):
    """KG Decision 엔티티"""

    id: str
    content: str
    status: DecisionStatus  # draft, latest, outdated, superseded, rejected
    context: str | None = None
    meeting_id: str | None = None  # Decision이 생성된 Meeting 스코프
    created_at: datetime
    updated_at: datetime | None = None

    # 관계 정보 (조회 시 포함)
    agenda_id: str | None = None
    agenda_topic: str | None = None
    meeting_title: str | None = None
    approvers: list[str] = []  # user_ids
    rejectors: list[str] = []  # user_ids

    # 버전 체인 정보 (타임라인 표시용)
    supersedes_id: str | None = None  # 이전 버전 Decision ID
