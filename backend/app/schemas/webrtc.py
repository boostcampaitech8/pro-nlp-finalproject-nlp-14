"""WebRTC 관련 Pydantic 스키마"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class SignalingMessageType(str, Enum):
    """시그널링 메시지 타입"""
    # Client -> Server
    JOIN = "join"
    OFFER = "offer"
    ANSWER = "answer"
    ICE_CANDIDATE = "ice-candidate"
    LEAVE = "leave"
    MUTE = "mute"
    # 녹음 관련 (Client -> Server)
    RECORDING_OFFER = "recording-offer"
    RECORDING_ICE = "recording-ice"
    RECORDING_STOP = "recording-stop"
    # 화면공유 관련 (Client -> Server)
    SCREEN_SHARE_START = "screen-share-start"
    SCREEN_SHARE_STOP = "screen-share-stop"
    SCREEN_OFFER = "screen-offer"
    SCREEN_ANSWER = "screen-answer"
    SCREEN_ICE_CANDIDATE = "screen-ice-candidate"
    # Server -> Client
    JOINED = "joined"
    PARTICIPANT_JOINED = "participant-joined"
    PARTICIPANT_LEFT = "participant-left"
    PARTICIPANT_MUTED = "participant-muted"
    ERROR = "error"
    # 녹음 관련 (Server -> Client)
    RECORDING_ANSWER = "recording-answer"
    RECORDING_STARTED = "recording-started"
    RECORDING_STOPPED = "recording-stopped"
    # 화면공유 관련 (Server -> Client)
    SCREEN_SHARE_STARTED = "screen-share-started"
    SCREEN_SHARE_STOPPED = "screen-share-stopped"


class RoomParticipant(BaseModel):
    """회의실 참여자 정보"""
    user_id: UUID = Field(serialization_alias="userId")
    user_name: str = Field(serialization_alias="userName")
    role: str
    audio_muted: bool = Field(default=False, serialization_alias="audioMuted")

    class Config:
        populate_by_name = True


class IceServer(BaseModel):
    """ICE 서버 설정"""
    urls: str
    username: str | None = None
    credential: str | None = None


class MeetingRoomResponse(BaseModel):
    """회의실 정보 응답"""
    meeting_id: UUID = Field(serialization_alias="meetingId")
    status: str
    participants: list[RoomParticipant]
    ice_servers: list[IceServer] = Field(serialization_alias="iceServers")
    max_participants: int = Field(default=10, serialization_alias="maxParticipants")

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


# ===== WebSocket 시그널링 메시지 스키마 =====

class JoinMessage(BaseModel):
    """회의 입장 메시지"""
    type: str = SignalingMessageType.JOIN


class OfferMessage(BaseModel):
    """SDP Offer 메시지"""
    type: str = SignalingMessageType.OFFER
    sdp: dict  # RTCSessionDescriptionInit


class AnswerMessage(BaseModel):
    """SDP Answer 메시지"""
    type: str = SignalingMessageType.ANSWER
    sdp: dict  # RTCSessionDescriptionInit
    target_user_id: str = Field(alias="targetUserId")

    class Config:
        populate_by_name = True


class IceCandidateMessage(BaseModel):
    """ICE Candidate 메시지"""
    type: str = SignalingMessageType.ICE_CANDIDATE
    candidate: dict  # RTCIceCandidateInit
    target_user_id: str | None = Field(default=None, alias="targetUserId")

    class Config:
        populate_by_name = True


class LeaveMessage(BaseModel):
    """회의 퇴장 메시지"""
    type: str = SignalingMessageType.LEAVE


class MuteMessage(BaseModel):
    """음소거 토글 메시지"""
    type: str = SignalingMessageType.MUTE
    muted: bool


# Server -> Client 메시지

class JoinedMessage(BaseModel):
    """입장 완료 메시지 (Server -> Client)"""
    type: str = SignalingMessageType.JOINED
    participants: list[RoomParticipant]


class ParticipantJoinedMessage(BaseModel):
    """다른 사용자 입장 알림"""
    type: str = SignalingMessageType.PARTICIPANT_JOINED
    participant: RoomParticipant


class ParticipantLeftMessage(BaseModel):
    """다른 사용자 퇴장 알림"""
    type: str = SignalingMessageType.PARTICIPANT_LEFT
    user_id: str = Field(serialization_alias="userId")

    class Config:
        populate_by_name = True


class ParticipantMutedMessage(BaseModel):
    """음소거 상태 변경 알림"""
    type: str = SignalingMessageType.PARTICIPANT_MUTED
    user_id: str = Field(serialization_alias="userId")
    muted: bool

    class Config:
        populate_by_name = True


class ErrorMessage(BaseModel):
    """에러 메시지"""
    type: str = SignalingMessageType.ERROR
    code: str
    message: str
