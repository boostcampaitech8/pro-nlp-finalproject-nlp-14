"""회의 트랜스크립트 모델"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TranscriptStatus(str, Enum):
    """트랜스크립트 상태"""

    PENDING = "pending"          # 대기 중
    PROCESSING = "processing"    # 처리 중
    COMPLETED = "completed"      # 완료
    FAILED = "failed"            # 실패


class MeetingTranscript(Base):
    """회의 전체 트랜스크립트 (화자별 병합 결과)"""

    __tablename__ = "meeting_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id"),
        nullable=False,
        unique=True,  # 회의당 1개
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=TranscriptStatus.PENDING.value,
        nullable=False,
    )

    # 병합된 결과
    full_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="전체 텍스트 (화자 라벨 포함)",
    )
    utterances: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="화자별 발화 목록",
    )

    # MinIO 파일 경로
    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="MinIO에 저장된 회의록 파일 경로",
    )

    # 메타데이터
    total_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    speaker_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    meeting_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="회의 실제 시작 시각",
    )
    meeting_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="회의 실제 종료 시각",
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="실패 시 에러 메시지",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # 관계
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="transcript")

    def __repr__(self) -> str:
        return f"<MeetingTranscript {self.id} for meeting {self.meeting_id}>"


# 순환 import 방지
from app.models.meeting import Meeting  # noqa: E402
