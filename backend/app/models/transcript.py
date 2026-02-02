"""새 transcripts 테이블 모델 (임시)"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Transcript(Base):
    """개별 발화 segment를 저장하는 테이블"""

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    start_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="발화 시작 시간 (밀리초)",
    )
    end_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="발화 종료 시간 (밀리초)",
    )
    start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="발화 시작 타임스탬프 (절대시간)",
    )
    transcript_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="전사된 텍스트",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="평균 신뢰도",
    )
    min_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="최소 신뢰도",
    )
    agent_call: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="에이전트 호출 여부",
    )
    agent_call_keyword: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="에이전트 호출 키워드",
    )
    agent_call_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="에이전트 호출 키워드 신뢰도",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="completed",
        nullable=False,
        comment="응답 상태 (completed/interrupted)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
