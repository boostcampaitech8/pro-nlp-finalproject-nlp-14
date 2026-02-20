from uuid import UUID

from pydantic import BaseModel, Field


class AddMeetingParticipantRequest(BaseModel):
    """회의 참여자 추가 요청"""

    user_id: UUID = Field(alias="userId")
    role: str = Field(default="participant")

    class Config:
        populate_by_name = True


class UpdateMeetingParticipantRequest(BaseModel):
    """회의 참여자 역할 수정 요청"""

    role: str
