"""네이버 OAuth 서비스"""

import secrets
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_tokens
from app.models.user import AuthProvider, User
from app.schemas.auth import AuthResponse, TokenResponse, UserResponse


class NaverOAuthService:
    """네이버 OAuth 인증 서비스"""

    # 네이버 OAuth 엔드포인트
    AUTHORIZE_URL = "https://nid.naver.com/oauth2.0/authorize"
    TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
    PROFILE_URL = "https://openapi.naver.com/v1/nid/me"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    def generate_state(self) -> str:
        """CSRF 방지용 상태 토큰 생성"""
        return secrets.token_urlsafe(32)

    def get_authorization_url(self, state: str) -> str:
        """네이버 OAuth 인증 URL 생성"""
        params = {
            "response_type": "code",
            "client_id": self.settings.naver_client_id,
            "redirect_uri": self.settings.naver_redirect_uri,
            "state": state,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def get_access_token(self, code: str, state: str) -> dict:
        """인증 코드로 Access Token 발급"""
        params = {
            "grant_type": "authorization_code",
            "client_id": self.settings.naver_client_id,
            "client_secret": self.settings.naver_client_secret,
            "code": code,
            "state": state,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, data=params)
            response.raise_for_status()
            data = response.json()

            # 에러 응답 처리
            if "error" in data:
                raise ValueError(f"Token error: {data.get('error_description', data['error'])}")

            return data

    async def get_user_profile(self, access_token: str) -> dict:
        """네이버 사용자 프로필 조회"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(self.PROFILE_URL, headers=headers)
            response.raise_for_status()
            data = response.json()

            # 에러 응답 처리
            if data.get("resultcode") != "00":
                raise ValueError(f"Profile error: {data.get('message', 'Unknown error')}")

            return data["response"]

    async def get_user_by_provider_id(self, provider_id: str) -> User | None:
        """provider_id로 사용자 조회"""
        result = await self.db.execute(
            select(User).where(
                User.provider_id == provider_id,
                User.auth_provider == AuthProvider.NAVER.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_or_update_user(self, profile: dict) -> User:
        """네이버 프로필로 사용자 생성 또는 업데이트"""
        provider_id = profile["id"]
        email = profile.get("email")
        name = profile.get("name") or profile.get("nickname") or "네이버 사용자"

        # 이메일이 없는 경우 provider_id 기반 이메일 생성
        if not email:
            email = f"naver_{provider_id}@naver.placeholder"

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
            # 기존 계정에 네이버 연동
            existing_user.auth_provider = AuthProvider.NAVER.value
            existing_user.provider_id = provider_id
            existing_user.name = name
            await self.db.flush()
            await self.db.refresh(existing_user)
            return existing_user

        # 신규 사용자 생성
        user = User(
            email=email,
            name=name,
            auth_provider=AuthProvider.NAVER.value,
            provider_id=provider_id,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(self, code: str, state: str) -> AuthResponse:
        """OAuth 콜백 처리 및 JWT 토큰 발급"""
        # 1. Access Token 발급
        token_data = await self.get_access_token(code, state)
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
