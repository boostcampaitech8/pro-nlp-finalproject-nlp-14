from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_tokens,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import AuthProvider, User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


class AuthService:
    """인증 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> User | None:
        """ID로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def register(self, data: RegisterRequest) -> AuthResponse:
        """회원가입"""
        # 이메일 중복 확인
        existing_user = await self.get_user_by_email(data.email)
        if existing_user:
            raise ValueError("EMAIL_EXISTS")

        # 사용자 생성
        user = User(
            email=data.email,
            name=data.name,
            hashed_password=get_password_hash(data.password),
            auth_provider=AuthProvider.LOCAL.value,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # 토큰 생성
        tokens = create_tokens(str(user.id))

        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=TokenResponse(**tokens),
        )

    async def login(self, data: LoginRequest) -> AuthResponse:
        """로그인"""
        # 사용자 조회
        user = await self.get_user_by_email(data.email)
        if not user:
            raise ValueError("INVALID_CREDENTIALS")

        # 비밀번호 검증
        if not user.hashed_password or not verify_password(
            data.password, user.hashed_password
        ):
            raise ValueError("INVALID_CREDENTIALS")

        # 토큰 생성
        tokens = create_tokens(str(user.id))

        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=TokenResponse(**tokens),
        )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """토큰 갱신"""
        # 토큰 검증
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("INVALID_TOKEN")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("INVALID_TOKEN")

        # 사용자 확인
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("USER_NOT_FOUND")

        # 새 토큰 생성
        tokens = create_tokens(str(user.id))
        return TokenResponse(**tokens)

    async def get_current_user(self, access_token: str) -> User:
        """현재 사용자 조회"""
        payload = decode_token(access_token)
        if not payload or payload.get("type") != "access":
            raise ValueError("INVALID_TOKEN")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("INVALID_TOKEN")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("USER_NOT_FOUND")

        return user
