"""녹음 관련 비즈니스 로직"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import MAX_RECORDING_FILE_SIZE, PRESIGNED_URL_EXPIRATION
from app.core.storage import storage_service
from app.models.recording import MeetingRecording, RecordingStatus

logger = logging.getLogger(__name__)


class RecordingService:
    """녹음 관련 비즈니스 로직을 처리하는 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_meeting_recordings(self, meeting_id: UUID) -> list[MeetingRecording]:
        """회의 녹음 목록 조회

        Args:
            meeting_id: 회의 ID

        Returns:
            녹음 목록 (user 정보 포함)
        """
        recordings_query = (
            select(MeetingRecording)
            .options(selectinload(MeetingRecording.user))
            .where(MeetingRecording.meeting_id == meeting_id)
            .order_by(MeetingRecording.started_at.desc())
        )
        result = await self.db.execute(recordings_query)
        return list(result.scalars().all())

    async def get_recording_by_id(
        self, recording_id: UUID, meeting_id: UUID
    ) -> MeetingRecording | None:
        """녹음 ID로 조회

        Args:
            recording_id: 녹음 ID
            meeting_id: 회의 ID (검증용)

        Returns:
            녹음 객체 또는 None
        """
        query = (
            select(MeetingRecording)
            .options(selectinload(MeetingRecording.user))
            .where(
                MeetingRecording.id == recording_id,
                MeetingRecording.meeting_id == meeting_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def validate_file_size(self, file_size: int) -> None:
        """파일 크기 검증

        Args:
            file_size: 파일 크기 (바이트)

        Raises:
            ValueError: 파일 크기가 제한을 초과하는 경우
        """
        if file_size > MAX_RECORDING_FILE_SIZE:
            raise ValueError("FILE_TOO_LARGE")

    async def create_recording_upload(
        self,
        meeting_id: UUID,
        user_id: UUID,
        file_size_bytes: int,
        started_at: datetime,
        ended_at: datetime,
        duration_ms: int,
    ) -> tuple[str, str, UUID]:
        """녹음 업로드를 위한 Presigned URL 생성

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            file_size_bytes: 파일 크기
            started_at: 녹음 시작 시간
            ended_at: 녹음 종료 시간
            duration_ms: 녹음 길이 (밀리초)

        Returns:
            (upload_url, file_path, recording_id) 튜플

        Raises:
            ValueError: 파일 크기가 제한을 초과하는 경우
        """
        # 파일 크기 검증
        self.validate_file_size(file_size_bytes)

        # Presigned URL 생성
        timestamp = started_at.strftime("%Y%m%d_%H%M%S")
        upload_url, file_path = storage_service.get_recording_upload_url(
            meeting_id=str(meeting_id),
            user_id=str(user_id),
            timestamp=timestamp,
        )

        # DB에 pending 상태로 저장
        recording = MeetingRecording(
            meeting_id=meeting_id,
            user_id=user_id,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            status=RecordingStatus.PENDING.value,
        )
        self.db.add(recording)
        await self.db.commit()
        await self.db.refresh(recording)

        logger.info(
            f"Recording upload URL generated: meeting={meeting_id}, user={user_id}, "
            f"recording={recording.id}"
        )

        return upload_url, file_path, recording.id

    async def upload_recording_directly(
        self,
        meeting_id: UUID,
        user_id: UUID,
        file_content: bytes,
        started_at: datetime,
        ended_at: datetime,
        duration_ms: int,
    ) -> MeetingRecording:
        """녹음 파일 직접 업로드

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            file_content: 파일 내용
            started_at: 녹음 시작 시간
            ended_at: 녹음 종료 시간
            duration_ms: 녹음 길이 (밀리초)

        Returns:
            생성된 녹음 객체

        Raises:
            ValueError: 파일 크기가 제한을 초과하는 경우
        """
        file_size = len(file_content)

        # 파일 크기 검증
        self.validate_file_size(file_size)

        # MinIO 업로드
        timestamp = started_at.strftime("%Y%m%d_%H%M%S")
        file_path = storage_service.upload_recording(
            meeting_id=str(meeting_id),
            user_id=str(user_id),
            timestamp=timestamp,
            data=file_content,
        )

        # DB 저장
        recording = MeetingRecording(
            meeting_id=meeting_id,
            user_id=user_id,
            file_path=file_path,
            file_size_bytes=file_size,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            status=RecordingStatus.COMPLETED.value,
        )
        self.db.add(recording)
        await self.db.commit()
        await self.db.refresh(recording)

        logger.info(
            f"Recording uploaded directly: meeting={meeting_id}, user={user_id}, "
            f"recording={recording.id}, size={file_size}"
        )

        return recording

    async def complete_recording_upload(
        self, recording_id: UUID, meeting_id: UUID
    ) -> MeetingRecording:
        """녹음 업로드 완료 확인

        Args:
            recording_id: 녹음 ID
            meeting_id: 회의 ID

        Returns:
            업데이트된 녹음 객체

        Raises:
            ValueError: 녹음을 찾을 수 없거나 파일이 존재하지 않는 경우
        """
        # 녹음 조회
        recording = await self.get_recording_by_id(recording_id, meeting_id)
        if not recording:
            raise ValueError("RECORDING_NOT_FOUND")

        # MinIO에서 파일 존재 여부 확인
        file_exists = storage_service.check_recording_exists(recording.file_path)
        if not file_exists:
            raise ValueError("FILE_NOT_FOUND")

        # 파일 크기 업데이트 (MinIO에서 실제 크기 조회)
        actual_size = storage_service.get_recording_size(recording.file_path)
        recording.file_size_bytes = actual_size
        recording.status = RecordingStatus.COMPLETED.value

        await self.db.commit()
        await self.db.refresh(recording)

        logger.info(
            f"Recording upload confirmed: recording={recording_id}, "
            f"size={actual_size}"
        )

        return recording

    def get_download_url(self, file_path: str) -> str:
        """녹음 다운로드 URL 생성

        Args:
            file_path: 파일 경로

        Returns:
            Presigned download URL
        """
        return storage_service.get_recording_url(file_path)

    def get_file_content(self, file_path: str) -> bytes:
        """녹음 파일 내용 조회

        Args:
            file_path: 파일 경로

        Returns:
            파일 내용 (바이트)
        """
        return storage_service.get_recording_file(file_path)
