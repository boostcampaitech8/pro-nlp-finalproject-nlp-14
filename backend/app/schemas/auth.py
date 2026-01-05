from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """회원가입 요청"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    name: str = Field(min_length=2, max_length=50)


class LoginRequest(BaseModel):
    """로그인 요청"""

    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """토큰 갱신 요청"""

    refresh_token: str = Field(alias="refreshToken")

    class Config:
        populate_by_name = True


class TokenResponse(BaseModel):
    """토큰 응답"""

    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")
    token_type: str = Field(default="Bearer", serialization_alias="tokenType")
    expires_in: int = Field(serialization_alias="expiresIn")

    class Config:
        populate_by_name = True


class UserResponse(BaseModel):
    """사용자 응답"""

    id: UUID
    email: str
    name: str
    auth_provider: str = Field(serialization_alias="authProvider")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class AuthResponse(BaseModel):
    """인증 응답 (토큰 + 사용자)"""

    user: UserResponse
    tokens: TokenResponse
