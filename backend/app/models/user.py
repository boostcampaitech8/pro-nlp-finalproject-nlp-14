import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthProvider(str, Enum):
    """인증 제공자"""

    LOCAL = "local"
    GOOGLE = "google"
    GITHUB = "github"


class User(Base):
    """사용자 모델"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # 소셜 로그인 사용자는 비밀번호 없음
    )
    auth_provider: Mapped[str] = mapped_column(
        String(20),
        default=AuthProvider.LOCAL.value,
        nullable=False,
    )
    provider_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # 소셜 로그인용 외부 ID
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
