from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_tokens, decode_token
from app.models.user import User
from app.schemas.auth import TokenResponse


class AuthService:
    """인증 서비스 (JWT 토큰 관리)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: str) -> User | None:
        """ID로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

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
