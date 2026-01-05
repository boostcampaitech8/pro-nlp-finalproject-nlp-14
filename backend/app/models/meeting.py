import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MeetingStatus(str, Enum):
    """회의 상태"""

    SCHEDULED = "scheduled"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class ParticipantRole(str, Enum):
    """회의 참여자 역할"""

    HOST = "host"
    PARTICIPANT = "participant"


class Meeting(Base):
    """회의 모델"""

    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=MeetingStatus.SCHEDULED.value,
        nullable=False,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    # 관계
    team: Mapped["Team"] = relationship("Team", back_populates="meetings")
    participants: Mapped[list["MeetingParticipant"]] = relationship(
        "MeetingParticipant",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    recordings: Mapped[list["MeetingRecording"]] = relationship(
        "MeetingRecording",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Meeting {self.title}>"


class MeetingParticipant(Base):
    """회의 참여자 모델"""

    __tablename__ = "meeting_participants"

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
    role: Mapped[str] = mapped_column(
        String(20),
        default=ParticipantRole.PARTICIPANT.value,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 관계
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="participants")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<MeetingParticipant {self.user_id} in {self.meeting_id}>"


# 순환 import 방지
from app.models.recording import MeetingRecording  # noqa: E402
from app.models.team import Team  # noqa: E402
from app.models.user import User  # noqa: E402
