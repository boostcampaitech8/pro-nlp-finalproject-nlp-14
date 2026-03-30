import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserActivityLog(Base):
    """사용자 활동 로그 모델"""

    __tablename__ = "user_activity_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )  # 비로그인 사용자도 추적
    session_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )  # page_view, click, scroll, input, form_submit
    event_target: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )  # 클릭한 요소 정보
    page_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    event_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # 추가 데이터 (좌표, scroll depth 등)
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )  # IPv6 지원
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<UserActivityLog {self.event_type} at {self.page_path}>"
