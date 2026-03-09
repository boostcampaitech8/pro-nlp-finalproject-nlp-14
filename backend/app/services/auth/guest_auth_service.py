"""게스트 인증 서비스"""

import random
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.neo4j_sync import neo4j_sync
from app.core.security import create_tokens
from app.models.user import AuthProvider, User
from app.schemas.auth import AuthResponse, TokenResponse, UserResponse


class GuestAuthService:
    """게스트 인증 서비스 - OAuth 없이 즉시 유저 생성 및 토큰 발급"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_guest_name(self) -> str:
        """게스트 닉네임 자동 생성 (Guest-XXXX)"""
        return f"Guest-{random.randint(1000, 9999)}"

    def _generate_guest_email(self) -> str:
        """게스트용 고유 placeholder email 생성"""
        return f"guest_{uuid.uuid4().hex[:12]}@guest.mit.local"

    async def authenticate(self) -> AuthResponse:
        """게스트 유저 생성 및 JWT 토큰 발급

        flush()만 수행하며, 실제 commit()은 get_db() dependency의
        context manager가 요청 종료 시 자동 수행.
        """
        # 1. 게스트 유저 생성
        guest_name = self._generate_guest_name()
        guest_email = self._generate_guest_email()

        user = User(
            email=guest_email,
            name=guest_name,
            auth_provider=AuthProvider.GUEST.value,
            provider_id=None,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # 2. Neo4j 동기화
        await neo4j_sync.sync_user_create(str(user.id), user.name, user.email)

        # 3. JWT 토큰 생성
        tokens = create_tokens(str(user.id))

        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=TokenResponse(**tokens),
        )
