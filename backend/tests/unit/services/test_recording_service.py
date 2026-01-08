"""RecordingService 단위 테스트

총 17개 테스트:
- validate_file_size: 2개 (유효한 크기, 초과)
- get_meeting_recordings: 3개 (성공, 빈 목록, 정렬)
- get_recording_by_id: 2개 (존재, 없음)
- create_recording_upload: 3개 (성공, 크기 초과, DB 저장)
- upload_recording_directly: 2개 (성공, 크기 초과)
- complete_recording_upload: 3개 (성공, 녹음 없음, 파일 없음)
- get_download_url: 1개 (성공)
- get_file_content: 1개 (성공)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4

from sqlalchemy import select

from app.core.constants import MAX_RECORDING_FILE_SIZE
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, ParticipantRole
from app.models.recording import MeetingRecording, RecordingStatus
from app.models.team import Team, TeamMember, TeamRole
from app.models.user import User
from app.services.recording_service import RecordingService


# ===== validate_file_size 테스트 (2개) =====


def test_validate_file_size_valid():
    """유효한 파일 크기 검증 통과"""
    service = RecordingService(db=MagicMock())

    # 100MB - 유효한 크기
    valid_size = 100 * 1024 * 1024

    # ValueError가 발생하지 않아야 함
    service.validate_file_size(valid_size)


def test_validate_file_size_too_large():
    """파일 크기 초과 시 ValueError 발생"""
    service = RecordingService(db=MagicMock())

    # 600MB - 최대 크기(500MB) 초과
    oversized = 600 * 1024 * 1024

    with pytest.raises(ValueError, match="FILE_TOO_LARGE"):
        service.validate_file_size(oversized)


# ===== get_meeting_recordings 테스트 (3개) =====


@pytest.mark.asyncio
async def test_get_meeting_recordings_success(
    db_session, test_meeting: Meeting, test_user: User
):
    """회의 녹음 목록 조회 성공"""
    service = RecordingService(db_session)

    # 녹음 생성
    recording = MeetingRecording(
        id=uuid4(),
        meeting_id=test_meeting.id,
        user_id=test_user.id,
        file_path="recordings/test/test.webm",
        file_size_bytes=1024 * 1024,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        duration_ms=300000,
        status=RecordingStatus.COMPLETED.value,
    )
    db_session.add(recording)
    await db_session.commit()

    result = await service.get_meeting_recordings(test_meeting.id)

    assert len(result) == 1
    assert result[0].id == recording.id
    assert result[0].meeting_id == test_meeting.id


@pytest.mark.asyncio
async def test_get_meeting_recordings_empty(
    db_session, test_meeting: Meeting
):
    """녹음이 없는 회의의 빈 목록"""
    service = RecordingService(db_session)

    result = await service.get_meeting_recordings(test_meeting.id)

    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_meeting_recordings_ordered_by_started_at(
    db_session, test_meeting: Meeting, test_user: User
):
    """녹음 목록이 started_at 내림차순 정렬"""
    service = RecordingService(db_session)

    base_time = datetime.now(timezone.utc)

    # 오래된 녹음
    old_recording = MeetingRecording(
        id=uuid4(),
        meeting_id=test_meeting.id,
        user_id=test_user.id,
        file_path="recordings/test/old.webm",
        file_size_bytes=1024,
        started_at=base_time - timedelta(hours=2),
        ended_at=base_time - timedelta(hours=1, minutes=50),
        duration_ms=600000,
        status=RecordingStatus.COMPLETED.value,
    )

    # 최신 녹음
    new_recording = MeetingRecording(
        id=uuid4(),
        meeting_id=test_meeting.id,
        user_id=test_user.id,
        file_path="recordings/test/new.webm",
        file_size_bytes=2048,
        started_at=base_time,
        ended_at=base_time + timedelta(minutes=10),
        duration_ms=600000,
        status=RecordingStatus.COMPLETED.value,
    )

    db_session.add_all([old_recording, new_recording])
    await db_session.commit()

    result = await service.get_meeting_recordings(test_meeting.id)

    assert len(result) == 2
    # 최신 녹음이 먼저
    assert result[0].id == new_recording.id
    assert result[1].id == old_recording.id


# ===== get_recording_by_id 테스트 (2개) =====


@pytest.mark.asyncio
async def test_get_recording_by_id_found(
    db_session, test_meeting: Meeting, test_user: User
):
    """녹음 ID로 조회 성공"""
    service = RecordingService(db_session)

    recording = MeetingRecording(
        id=uuid4(),
        meeting_id=test_meeting.id,
        user_id=test_user.id,
        file_path="recordings/test/test.webm",
        file_size_bytes=1024,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        duration_ms=300000,
        status=RecordingStatus.COMPLETED.value,
    )
    db_session.add(recording)
    await db_session.commit()

    result = await service.get_recording_by_id(recording.id, test_meeting.id)

    assert result is not None
    assert result.id == recording.id


@pytest.mark.asyncio
async def test_get_recording_by_id_not_found(
    db_session, test_meeting: Meeting
):
    """존재하지 않는 녹음 ID 조회"""
    service = RecordingService(db_session)

    fake_id = uuid4()

    result = await service.get_recording_by_id(fake_id, test_meeting.id)

    assert result is None


# ===== create_recording_upload 테스트 (3개) =====


@pytest.mark.asyncio
async def test_create_recording_upload_success(
    db_session, test_meeting: Meeting, test_user: User
):
    """녹음 업로드 URL 생성 성공"""
    service = RecordingService(db_session)

    with patch("app.services.recording_service.storage_service") as mock_storage:
        mock_storage.get_recording_upload_url.return_value = (
            "https://minio.test/upload-url",
            "recordings/test/file.webm",
        )

        started_at = datetime.now(timezone.utc)
        ended_at = started_at + timedelta(minutes=10)

        upload_url, file_path, recording_id = await service.create_recording_upload(
            meeting_id=test_meeting.id,
            user_id=test_user.id,
            file_size_bytes=50 * 1024 * 1024,  # 50MB
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=600000,
        )

        assert upload_url == "https://minio.test/upload-url"
        assert file_path == "recordings/test/file.webm"
        assert recording_id is not None

        # DB에 저장 확인
        recording = await service.get_recording_by_id(recording_id, test_meeting.id)
        assert recording is not None
        assert recording.status == RecordingStatus.PENDING.value


@pytest.mark.asyncio
async def test_create_recording_upload_file_too_large(
    db_session, test_meeting: Meeting, test_user: User
):
    """파일 크기 초과 시 업로드 URL 생성 실패"""
    service = RecordingService(db_session)

    started_at = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="FILE_TOO_LARGE"):
        await service.create_recording_upload(
            meeting_id=test_meeting.id,
            user_id=test_user.id,
            file_size_bytes=600 * 1024 * 1024,  # 600MB - 초과
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=10),
            duration_ms=600000,
        )


@pytest.mark.asyncio
async def test_create_recording_upload_saves_to_db(
    db_session, test_meeting: Meeting, test_user: User
):
    """업로드 URL 생성 시 DB에 PENDING 상태로 저장"""
    service = RecordingService(db_session)

    with patch("app.services.recording_service.storage_service") as mock_storage:
        mock_storage.get_recording_upload_url.return_value = (
            "https://minio.test/upload-url",
            "recordings/test/file.webm",
        )

        started_at = datetime.now(timezone.utc)

        _, _, recording_id = await service.create_recording_upload(
            meeting_id=test_meeting.id,
            user_id=test_user.id,
            file_size_bytes=10 * 1024 * 1024,
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=5),
            duration_ms=300000,
        )

        # DB에서 직접 조회
        result = await db_session.execute(
            select(MeetingRecording).where(MeetingRecording.id == recording_id)
        )
        saved_recording = result.scalar_one_or_none()

        assert saved_recording is not None
        assert saved_recording.status == RecordingStatus.PENDING.value
        assert saved_recording.file_path == "recordings/test/file.webm"


# ===== upload_recording_directly 테스트 (2개) =====


@pytest.mark.asyncio
async def test_upload_recording_directly_success(
    db_session, test_meeting: Meeting, test_user: User
):
    """녹음 파일 직접 업로드 성공"""
    service = RecordingService(db_session)

    with patch("app.services.recording_service.storage_service") as mock_storage:
        mock_storage.upload_recording.return_value = "recordings/test/uploaded.webm"

        file_content = b"test audio data" * 1000  # 약 15KB
        started_at = datetime.now(timezone.utc)

        result = await service.upload_recording_directly(
            meeting_id=test_meeting.id,
            user_id=test_user.id,
            file_content=file_content,
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=3),
            duration_ms=180000,
        )

        assert result is not None
        assert result.status == RecordingStatus.COMPLETED.value
        assert result.file_path == "recordings/test/uploaded.webm"
        assert result.file_size_bytes == len(file_content)


@pytest.mark.asyncio
async def test_upload_recording_directly_file_too_large(
    db_session, test_meeting: Meeting, test_user: User
):
    """직접 업로드 시 파일 크기 초과"""
    service = RecordingService(db_session)

    # 매우 큰 파일 (600MB 이상)
    # 실제로 600MB 바이트를 만들지 않고, validate_file_size만 테스트
    with patch.object(service, "validate_file_size", side_effect=ValueError("FILE_TOO_LARGE")):
        with pytest.raises(ValueError, match="FILE_TOO_LARGE"):
            await service.upload_recording_directly(
                meeting_id=test_meeting.id,
                user_id=test_user.id,
                file_content=b"small content",  # 실제 크기와 무관하게 mock에서 예외 발생
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                duration_ms=600000,
            )


# ===== complete_recording_upload 테스트 (3개) =====


@pytest.mark.asyncio
async def test_complete_recording_upload_success(
    db_session, test_meeting: Meeting, test_user: User
):
    """녹음 업로드 완료 확인 성공"""
    service = RecordingService(db_session)

    # PENDING 상태의 녹음 생성
    recording = MeetingRecording(
        id=uuid4(),
        meeting_id=test_meeting.id,
        user_id=test_user.id,
        file_path="recordings/test/pending.webm",
        file_size_bytes=1024,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        duration_ms=300000,
        status=RecordingStatus.PENDING.value,
    )
    db_session.add(recording)
    await db_session.commit()

    with patch("app.services.recording_service.storage_service") as mock_storage:
        mock_storage.check_recording_exists.return_value = True
        mock_storage.get_recording_size.return_value = 2048  # 실제 파일 크기

        result = await service.complete_recording_upload(recording.id, test_meeting.id)

        assert result.status == RecordingStatus.COMPLETED.value
        assert result.file_size_bytes == 2048


@pytest.mark.asyncio
async def test_complete_recording_upload_recording_not_found(
    db_session, test_meeting: Meeting
):
    """존재하지 않는 녹음 완료 시도"""
    service = RecordingService(db_session)

    fake_id = uuid4()

    with pytest.raises(ValueError, match="RECORDING_NOT_FOUND"):
        await service.complete_recording_upload(fake_id, test_meeting.id)


@pytest.mark.asyncio
async def test_complete_recording_upload_file_not_found(
    db_session, test_meeting: Meeting, test_user: User
):
    """파일이 MinIO에 없는 경우"""
    service = RecordingService(db_session)

    # PENDING 상태의 녹음 생성
    recording = MeetingRecording(
        id=uuid4(),
        meeting_id=test_meeting.id,
        user_id=test_user.id,
        file_path="recordings/test/missing.webm",
        file_size_bytes=1024,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        duration_ms=300000,
        status=RecordingStatus.PENDING.value,
    )
    db_session.add(recording)
    await db_session.commit()

    with patch("app.services.recording_service.storage_service") as mock_storage:
        mock_storage.check_recording_exists.return_value = False

        with pytest.raises(ValueError, match="FILE_NOT_FOUND"):
            await service.complete_recording_upload(recording.id, test_meeting.id)


# ===== get_download_url 테스트 (1개) =====


def test_get_download_url_success():
    """다운로드 URL 생성 성공"""
    service = RecordingService(db=MagicMock())

    with patch("app.services.recording_service.storage_service") as mock_storage:
        mock_storage.get_recording_url.return_value = "https://minio.test/download-url"

        result = service.get_download_url("recordings/test/file.webm")

        assert result == "https://minio.test/download-url"
        mock_storage.get_recording_url.assert_called_once_with("recordings/test/file.webm")


# ===== get_file_content 테스트 (1개) =====


def test_get_file_content_success():
    """파일 내용 조회 성공"""
    service = RecordingService(db=MagicMock())

    with patch("app.services.recording_service.storage_service") as mock_storage:
        mock_storage.get_recording_file.return_value = b"test audio content"

        result = service.get_file_content("recordings/test/file.webm")

        assert result == b"test audio content"
        mock_storage.get_recording_file.assert_called_once_with("recordings/test/file.webm")
