"""Context/Topic API 스키마"""

from datetime import datetime

from pydantic import BaseModel, Field


class TopicItem(BaseModel):
    """개별 토픽 항목"""

    id: str  # 토픽 고유 ID
    name: str  # 토픽 제목
    summary: str  # 토픽 요약 (120자 이내)
    start_turn: int = Field(serialization_alias="startTurn")  # 시작 발화 번호
    end_turn: int = Field(serialization_alias="endTurn")  # 종료 발화 번호
    keywords: list[str] = Field(default_factory=list)  # 키워드 목록

    class Config:
        populate_by_name = True


class TopicFeedResponse(BaseModel):
    """GET /meetings/{meeting_id}/context/topics 응답"""

    meeting_id: str = Field(serialization_alias="meetingId")  # 회의 ID
    pending_chunks: int = Field(serialization_alias="pendingChunks")  # 대기 중인 청크 수
    is_l1_running: bool = Field(serialization_alias="isL1Running")  # L1 처리 진행 중 여부
    current_topic: str | None = Field(
        default=None, serialization_alias="currentTopic"
    )  # 현재 토픽
    topics: list[TopicItem] = Field(default_factory=list)  # 토픽 목록 (최신순)
    updated_at: datetime = Field(serialization_alias="updatedAt")  # 마지막 업데이트 시각

    class Config:
        populate_by_name = True
