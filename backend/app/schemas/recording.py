"""녹음 관련 Pydantic 스키마"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RecordingUploadRequest(BaseModel):
    """녹음 업로드 메타데이터 요청 (기존 방식 - deprecated)"""

    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime = Field(alias="endedAt")
    duration_ms: int = Field(alias="durationMs")

    class Config:
        populate_by_name = True


class RecordingUploadUrlRequest(BaseModel):
    """Presigned URL 요청"""

    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime = Field(alias="endedAt")
    duration_ms: int = Field(alias="durationMs")
    file_size_bytes: int = Field(alias="fileSizeBytes")

    class Config:
        populate_by_name = True


class RecordingUploadUrlResponse(BaseModel):
    """Presigned URL 응답"""

    recording_id: UUID = Field(serialization_alias="recordingId")
    upload_url: str = Field(serialization_alias="uploadUrl")
    file_path: str = Field(serialization_alias="filePath")
    expires_in_seconds: int = Field(default=3600, serialization_alias="expiresInSeconds")

    class Config:
        populate_by_name = True


class RecordingConfirmRequest(BaseModel):
    """업로드 완료 확인 요청"""

    file_size_bytes: int | None = Field(default=None, alias="fileSizeBytes")

    class Config:
        populate_by_name = True


class RecordingResponse(BaseModel):
    """녹음 정보 응답"""

    id: UUID
    meeting_id: UUID = Field(serialization_alias="meetingId")
    user_id: UUID = Field(serialization_alias="userId")
    user_name: str | None = Field(default=None, serialization_alias="userName")
    status: str
    started_at: datetime = Field(serialization_alias="startedAt")
    ended_at: datetime | None = Field(default=None, serialization_alias="endedAt")
    duration_ms: int | None = Field(default=None, serialization_alias="durationMs")
    file_size_bytes: int | None = Field(default=None, serialization_alias="fileSizeBytes")
    created_at: datetime = Field(serialization_alias="createdAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class RecordingListResponse(BaseModel):
    """녹음 목록 응답"""

    recordings: list[RecordingResponse]
    total: int


class RecordingDownloadResponse(BaseModel):
    """녹음 다운로드 URL 응답"""

    recording_id: UUID = Field(serialization_alias="recordingId")
    download_url: str = Field(serialization_alias="downloadUrl")
    expires_in_seconds: int = Field(default=3600, serialization_alias="expiresInSeconds")

    class Config:
        populate_by_name = True
