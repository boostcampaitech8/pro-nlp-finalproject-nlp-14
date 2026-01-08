"""녹음 파일 저장 및 DB 영속화 - RecordingSession의 저장 책임 분리"""

import logging
import os
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage_service
from app.models.recording import MeetingRecording, RecordingStatus

logger = logging.getLogger(__name__)


class RecordingPersistence:
    """녹음 파일 업로드 및 DB 저장 처리

    RecordingSession의 저장/영속화 책임을 분리한 클래스.
    MinIO 업로드, DB 레코드 생성, 임시 파일 정리를 담당.
    """

    async def save_recording(
        self,
        meeting_id: UUID,
        user_id: UUID,
        temp_file_path: str,
        started_at: datetime,
        ended_at: datetime,
        db: AsyncSession,
    ) -> MeetingRecording | None:
        """녹음 파일을 MinIO에 업로드하고 DB에 저장

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            temp_file_path: 임시 파일 경로
            started_at: 녹음 시작 시각
            ended_at: 녹음 종료 시각
            db: 데이터베이스 세션

        Returns:
            저장된 MeetingRecording 또는 None (파일이 없거나 빈 경우)
        """
        # 파일 존재 확인
        if not os.path.exists(temp_file_path):
            logger.warning(f"[RecordingPersistence] Temp file not found: {temp_file_path}")
            return None

        # 파일 크기 확인
        file_size = os.path.getsize(temp_file_path)
        if file_size == 0:
            logger.warning(f"[RecordingPersistence] Empty recording file for user {user_id}")
            return None

        try:
            # MinIO 업로드
            timestamp = started_at.strftime("%Y%m%d_%H%M%S")
            file_path = storage_service.upload_recording_file(
                meeting_id=str(meeting_id),
                user_id=str(user_id),
                timestamp=timestamp,
                file_path=temp_file_path,
            )

            # DB 저장
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)
            recording = MeetingRecording(
                meeting_id=meeting_id,
                user_id=user_id,
                file_path=file_path,
                status=RecordingStatus.COMPLETED.value,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=duration_ms,
                file_size_bytes=file_size,
            )
            db.add(recording)
            await db.commit()
            await db.refresh(recording)

            logger.info(
                f"[RecordingPersistence] Recording saved: {file_path} "
                f"({duration_ms}ms, {file_size} bytes)"
            )
            return recording

        except Exception as e:
            logger.error(f"[RecordingPersistence] Failed to save recording: {e}")
            raise
        finally:
            # 임시 파일 정리
            self._cleanup_temp_file(temp_file_path)

    def _cleanup_temp_file(self, file_path: str) -> None:
        """임시 파일 삭제

        Args:
            file_path: 삭제할 파일 경로
        """
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
                logger.debug(f"[RecordingPersistence] Temp file deleted: {file_path}")
            except Exception as e:
                logger.warning(f"[RecordingPersistence] Failed to delete temp file: {e}")
