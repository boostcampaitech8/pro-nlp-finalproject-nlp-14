"""회의 녹음 모델"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RecordingStatus(str, Enum):
    """녹음 상태"""

    RECORDING = "recording"      # 녹음 중
    COMPLETED = "completed"      # 녹음 완료
    FAILED = "failed"            # 녹음 실패


class MeetingRecording(Base):
    """회의 녹음 메타데이터"""

    __tablename__ = "meeting_recordings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=RecordingStatus.RECORDING.value,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 관계
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="recordings")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<MeetingRecording {self.id} for user {self.user_id}>"


# 순환 import 방지
from app.models.meeting import Meeting  # noqa: E402
from app.models.user import User  # noqa: E402
