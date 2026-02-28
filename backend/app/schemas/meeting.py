from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse
from app.schemas.team import PaginationMeta


class CreateMeetingRequest(BaseModel):
    """회의 생성 요청"""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    scheduled_at: datetime | None = Field(default=None, alias="scheduledAt")

    class Config:
        populate_by_name = True


class UpdateMeetingRequest(BaseModel):
    """회의 수정 요청"""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    scheduled_at: datetime | None = Field(default=None, alias="scheduledAt")
    status: str | None = None

    class Config:
        populate_by_name = True


class MeetingResponse(BaseModel):
    """회의 응답"""

    id: UUID
    team_id: UUID = Field(serialization_alias="teamId")
    title: str
    description: str | None
    created_by: UUID = Field(serialization_alias="createdBy")
    status: str
    scheduled_at: datetime | None = Field(serialization_alias="scheduledAt")
    started_at: datetime | None = Field(serialization_alias="startedAt")
    ended_at: datetime | None = Field(serialization_alias="endedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class MeetingParticipantResponse(BaseModel):
    """회의 참여자 응답"""

    id: UUID
    meeting_id: UUID = Field(serialization_alias="meetingId")
    user_id: UUID = Field(serialization_alias="userId")
    user: UserResponse | None = None
    role: str
    joined_at: datetime = Field(serialization_alias="joinedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class MeetingWithParticipantsResponse(BaseModel):
    """회의 상세 응답 (참여자 포함)"""

    id: UUID
    team_id: UUID = Field(serialization_alias="teamId")
    title: str
    description: str | None
    created_by: UUID = Field(serialization_alias="createdBy")
    status: str
    scheduled_at: datetime | None = Field(serialization_alias="scheduledAt")
    started_at: datetime | None = Field(serialization_alias="startedAt")
    ended_at: datetime | None = Field(serialization_alias="endedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    participants: list[MeetingParticipantResponse]

    class Config:
        populate_by_name = True
        from_attributes = True


class MeetingListResponse(BaseModel):
    """회의 목록 응답"""

    items: list[MeetingResponse]
    meta: PaginationMeta
