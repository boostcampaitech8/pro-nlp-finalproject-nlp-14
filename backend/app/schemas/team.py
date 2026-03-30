from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse


class CreateTeamRequest(BaseModel):
    """팀 생성 요청"""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class UpdateTeamRequest(BaseModel):
    """팀 수정 요청"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class TeamResponse(BaseModel):
    """팀 응답"""

    id: UUID
    name: str
    description: str | None
    created_by: UUID = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class TeamMemberResponse(BaseModel):
    """팀 멤버 응답"""

    id: UUID
    team_id: UUID = Field(serialization_alias="teamId")
    user_id: UUID = Field(serialization_alias="userId")
    user: UserResponse | None = None
    role: str
    joined_at: datetime = Field(serialization_alias="joinedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class TeamWithMembersResponse(BaseModel):
    """팀 상세 응답 (멤버 포함)"""

    id: UUID
    name: str
    description: str | None
    created_by: UUID = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    members: list[TeamMemberResponse]

    class Config:
        populate_by_name = True
        from_attributes = True


class PaginationMeta(BaseModel):
    """페이지네이션 메타"""

    page: int
    limit: int
    total: int
    total_pages: int = Field(serialization_alias="totalPages")

    class Config:
        populate_by_name = True


class TeamListResponse(BaseModel):
    """팀 목록 응답"""

    items: list[TeamResponse]
    meta: PaginationMeta
