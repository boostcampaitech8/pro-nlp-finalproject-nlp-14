"""LiveKit 기반 회의 관련 Pydantic 스키마"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoomParticipant(BaseModel):
    """회의실 참여자 정보"""
    user_id: UUID = Field(serialization_alias="userId")
    user_name: str = Field(serialization_alias="userName")
    role: str
    audio_muted: bool = Field(default=False, serialization_alias="audioMuted")

    class Config:
        populate_by_name = True


class StartMeetingResponse(BaseModel):
    """회의 시작 응답"""
    meeting_id: UUID = Field(serialization_alias="meetingId")
    status: str
    started_at: datetime = Field(serialization_alias="startedAt")

    class Config:
        populate_by_name = True


class EndMeetingResponse(BaseModel):
    """회의 종료 응답"""
    meeting_id: UUID = Field(serialization_alias="meetingId")
    status: str
    ended_at: datetime = Field(serialization_alias="endedAt")

    class Config:
        populate_by_name = True


# ===== LiveKit 관련 스키마 =====


class LiveKitTokenResponse(BaseModel):
    """LiveKit 토큰 응답"""

    token: str
    ws_url: str = Field(serialization_alias="wsUrl")
    room_name: str = Field(serialization_alias="roomName")

    class Config:
        populate_by_name = True


class LiveKitRoomResponse(BaseModel):
    """LiveKit 룸 정보 응답"""

    meeting_id: UUID = Field(serialization_alias="meetingId")
    room_name: str = Field(serialization_alias="roomName")
    status: str
    participants: list[RoomParticipant]
    max_participants: int = Field(default=20, serialization_alias="maxParticipants")
    ws_url: str = Field(serialization_alias="wsUrl")
    token: str

    class Config:
        populate_by_name = True


class StartRecordingResponse(BaseModel):
    """녹음 시작 응답"""

    meeting_id: UUID = Field(serialization_alias="meetingId")
    egress_id: str = Field(serialization_alias="egressId")
    started_at: datetime = Field(serialization_alias="startedAt")

    class Config:
        populate_by_name = True


class StopRecordingResponse(BaseModel):
    """녹음 중지 응답"""

    meeting_id: UUID = Field(serialization_alias="meetingId")
    stopped_at: datetime = Field(serialization_alias="stoppedAt")

    class Config:
        populate_by_name = True
