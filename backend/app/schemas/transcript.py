"""트랜스크립트 관련 Pydantic 스키마"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    """STT 시작 요청"""

    language: str = Field(default="ko", description="우선 언어 코드")


class TranscribeResponse(BaseModel):
    """STT 시작 응답"""

    transcript_id: UUID = Field(serialization_alias="transcriptId")
    status: str
    message: str | None = None

    class Config:
        populate_by_name = True


class TranscriptStatusResponse(BaseModel):
    """STT 진행 상태 응답"""

    transcript_id: UUID = Field(serialization_alias="transcriptId")
    status: str
    total_recordings: int = Field(serialization_alias="totalRecordings")
    processed_recordings: int = Field(serialization_alias="processedRecordings")
    error: str | None = None

    class Config:
        populate_by_name = True


class TranscriptSegmentResponse(BaseModel):
    """트랜스크립트 세그먼트"""

    id: int
    start_ms: int = Field(serialization_alias="startMs")
    end_ms: int = Field(serialization_alias="endMs")
    text: str

    class Config:
        populate_by_name = True


class UtteranceResponse(BaseModel):
    """화자별 발화"""

    id: int
    speaker_id: str = Field(serialization_alias="speakerId")
    speaker_name: str = Field(serialization_alias="speakerName")
    start_ms: int = Field(serialization_alias="startMs")
    end_ms: int = Field(serialization_alias="endMs")
    text: str
    timestamp: datetime  # 실제 발화 시각 (wall-clock time)

    class Config:
        populate_by_name = True


class MeetingTranscriptResponse(BaseModel):
    """회의 트랜스크립트 응답"""

    id: UUID
    meeting_id: UUID = Field(serialization_alias="meetingId")
    status: str
    full_text: str | None = Field(default=None, serialization_alias="fullText")
    utterances: list[UtteranceResponse] | None = None
    total_duration_ms: int | None = Field(default=None, serialization_alias="totalDurationMs")
    speaker_count: int | None = Field(default=None, serialization_alias="speakerCount")
    meeting_start: datetime | None = Field(default=None, serialization_alias="meetingStart")
    meeting_end: datetime | None = Field(default=None, serialization_alias="meetingEnd")
    file_path: str | None = Field(default=None, serialization_alias="filePath")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")
    error: str | None = None

    class Config:
        populate_by_name = True
        from_attributes = True


class TranscriptDownloadResponse(BaseModel):
    """회의록 다운로드 URL 응답"""

    meeting_id: UUID = Field(serialization_alias="meetingId")
    download_url: str = Field(serialization_alias="downloadUrl")
    expires_in_seconds: int = Field(serialization_alias="expiresInSeconds")

    class Config:
        populate_by_name = True
