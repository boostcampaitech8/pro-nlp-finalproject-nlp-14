"""새 Transcript Service용 Pydantic 스키마 (임시)"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ===== POST /meetings/{id}/transcripts =====

class CreateTranscriptRequest(BaseModel):
    """발화 segment 생성 요청 (Worker → Backend)"""

    meeting_id: UUID = Field(serialization_alias="meetingId", validation_alias="meetingId")
    user_id: UUID = Field(serialization_alias="userId", validation_alias="userId")
    start_ms: int = Field(serialization_alias="startMs", validation_alias="startMs", ge=0)
    end_ms: int = Field(serialization_alias="endMs", validation_alias="endMs")
    text: str = Field(min_length=1)
    confidence: float
    min_confidence: float = Field(serialization_alias="minConfidence", validation_alias="minConfidence")
    agent_call: bool = Field(
        default=False,
        serialization_alias="agentCall",
        validation_alias="agentCall",
    )
    agent_call_keyword: str | None = Field(
        default=None,
        serialization_alias="agentCallKeyword",
        validation_alias="agentCallKeyword",
        max_length=50,
    )
    agent_call_confidence: float | None = Field(
        default=None,
        serialization_alias="agentCallConfidence",
        validation_alias="agentCallConfidence",
    )

    class Config:
        populate_by_name = True


class CreateTranscriptResponse(BaseModel):
    """발화 segment 생성 응답"""

    id: UUID
    created_at: datetime = Field(serialization_alias="createdAt")

    class Config:
        populate_by_name = True


# ===== GET /meetings/{meeting_id}/transcripts =====

class UtteranceItem(BaseModel):
    """개별 발화 아이템"""

    id: UUID
    speaker_id: UUID = Field(serialization_alias="speakerId")
    speaker_name: str = Field(serialization_alias="speakerName")
    start_ms: int = Field(serialization_alias="startMs")
    end_ms: int = Field(serialization_alias="endMs")
    text: str
    timestamp: datetime

    class Config:
        populate_by_name = True


class GetMeetingTranscriptsResponse(BaseModel):
    """회의 전체 전사 조회 응답"""

    meeting_id: UUID = Field(serialization_alias="meetingId")
    status: str
    full_text: str = Field(serialization_alias="fullText")
    utterances: list[UtteranceItem]
    total_duration_ms: int = Field(serialization_alias="totalDurationMs")
    speaker_count: int = Field(serialization_alias="speakerCount")
    meeting_start: datetime | None = Field(default=None, serialization_alias="meetingStart")
    meeting_end: datetime | None = Field(default=None, serialization_alias="meetingEnd")
    created_at: datetime = Field(serialization_alias="createdAt")

    class Config:
        populate_by_name = True
