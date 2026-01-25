"""Google OAuth 서비스"""

import secrets
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_tokens
from app.models.user import AuthProvider, User
from app.schemas.auth import AuthResponse, TokenResponse, UserResponse


class GoogleOAuthService:
    """Google OAuth 인증 서비스"""

    # Google OAuth 엔드포인트 (공식 문서 기준)
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    # OpenID Connect scope (이메일, 프로필 정보 포함)
    SCOPE = "openid email profile"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    def generate_state(self) -> str:
        """CSRF 방지용 상태 토큰 생성"""
        return secrets.token_urlsafe(32)

    def get_authorization_url(self, state: str) -> str:
        """Google OAuth 인증 URL 생성"""
        params = {
            "response_type": "code",
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "scope": self.SCOPE,
            "state": state,
            "access_type": "offline",  # refresh token 획득
            "prompt": "consent",  # 항상 동의 화면 표시 (refresh token 보장)
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def get_access_token(self, code: str) -> dict:
        """인증 코드로 Access Token 발급"""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret,
            "code": code,
            "redirect_uri": self.settings.google_redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

            # 에러 응답 처리
            if "error" in token_data:
                raise ValueError(
                    f"Token error: {token_data.get('error_description', token_data['error'])}"
                )

            return token_data

    async def get_user_profile(self, access_token: str) -> dict:
        """Google 사용자 프로필 조회"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(self.USERINFO_URL, headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_user_by_provider_id(self, provider_id: str) -> User | None:
        """provider_id로 사용자 조회"""
        result = await self.db.execute(
            select(User).where(
                User.provider_id == provider_id,
                User.auth_provider == AuthProvider.GOOGLE.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_or_update_user(self, profile: dict) -> User:
        """Google 프로필로 사용자 생성 또는 업데이트"""
        # sub 필드를 provider_id로 사용 (Google 권장)
        provider_id = profile["sub"]
        email = profile.get("email")
        name = profile.get("name") or profile.get("given_name") or "Google 사용자"

        # 이메일이 없는 경우 provider_id 기반 이메일 생성
        if not email:
            email = f"google_{provider_id}@google.placeholder"

        # 기존 사용자 조회 (provider_id 기준)
        user = await self.get_user_by_provider_id(provider_id)

        if user:
            # 기존 사용자 정보 업데이트
            user.name = name
            if profile.get("email"):
                user.email = profile["email"]
            await self.db.flush()
            await self.db.refresh(user)
            return user

        # 이메일로 기존 사용자 조회 (다른 방식으로 가입한 경우)
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            # 기존 계정에 Google 연동
            existing_user.auth_provider = AuthProvider.GOOGLE.value
            existing_user.provider_id = provider_id
            existing_user.name = name
            await self.db.flush()
            await self.db.refresh(existing_user)
            return existing_user

        # 신규 사용자 생성
        user = User(
            email=email,
            name=name,
            auth_provider=AuthProvider.GOOGLE.value,
            provider_id=provider_id,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(self, code: str) -> AuthResponse:
        """OAuth 콜백 처리 및 JWT 토큰 발급"""
        # 1. Access Token 발급
        token_data = await self.get_access_token(code)
        access_token = token_data["access_token"]

        # 2. 사용자 프로필 조회
        profile = await self.get_user_profile(access_token)

        # 3. 사용자 생성/업데이트
        user = await self.create_or_update_user(profile)

        # 4. JWT 토큰 생성
        tokens = create_tokens(str(user.id))

        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=TokenResponse(**tokens),
        )
