from pydantic import BaseModel, EmailStr, Field


class InviteTeamMemberRequest(BaseModel):
    """팀 멤버 초대 요청"""

    email: EmailStr
    role: str = Field(default="member")


class UpdateTeamMemberRequest(BaseModel):
    """팀 멤버 역할 수정 요청"""

    role: str
