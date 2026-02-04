from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InviteLinkResponse(BaseModel):
    """초대 링크 응답"""

    code: str
    invite_url: str = Field(serialization_alias="inviteUrl")
    team_id: UUID = Field(serialization_alias="teamId")
    created_by: UUID = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    expires_at: datetime = Field(serialization_alias="expiresAt")

    class Config:
        populate_by_name = True


class InvitePreviewResponse(BaseModel):
    """초대 링크 미리보기 응답 (비인증)"""

    team_name: str = Field(serialization_alias="teamName")
    team_description: str | None = Field(serialization_alias="teamDescription")
    member_count: int = Field(serialization_alias="memberCount")
    max_members: int = Field(serialization_alias="maxMembers")

    class Config:
        populate_by_name = True


class AcceptInviteResponse(BaseModel):
    """초대 수락 응답"""

    team_id: UUID = Field(serialization_alias="teamId")
    role: str
    message: str = "팀에 성공적으로 가입했습니다"

    class Config:
        populate_by_name = True
