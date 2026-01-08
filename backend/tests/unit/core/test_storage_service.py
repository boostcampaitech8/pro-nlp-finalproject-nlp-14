"""스토리지 서비스 단위 테스트

총 20개 테스트:
- upload_recording: 3개 (성공, 경로 형식, 콘텐츠 타입)
- upload_recording_file: 2개 (성공, 에러 처리)
- get_recording_upload_url: 3개 (성공, 반환값, 만료시간)
- check_file_exists: 3개 (존재, 없음, 에러 처리)
- get_file_info: 3개 (성공, 없음, 에러 처리)
- get_recording_url: 2개 (성공, 만료시간)
- get_recording_file: 2개 (성공, 에러 처리)
- delete_recording: 2개 (성공, 에러 처리)
"""

import pytest
from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch
from minio.error import S3Error

from app.core.storage import StorageService


# ===== Fixtures =====


@pytest.fixture
def storage_service():
    """테스트용 StorageService 인스턴스"""
    return StorageService()


@pytest.fixture
def mock_minio_client():
    """Mock MinIO 클라이언트"""
    client = MagicMock()
    # 기본 설정
    client.bucket_exists.return_value = True
    client.stat_object.return_value = Mock(
        size=1024 * 1024,
        content_type="audio/webm",
        last_modified="2026-01-08T12:00:00Z",
        etag="test-etag",
    )
    client.presigned_get_object.return_value = "https://minio.test/presigned-get-url"
    client.presigned_put_object.return_value = "http://localhost:9000/recordings/test-path.webm?signature=abc"
    client.get_object.return_value = Mock(
        read=lambda: b"test file content",
        close=lambda: None,
        release_conn=lambda: None,
    )
    return client


@pytest.fixture
def mock_settings():
    """Mock settings"""
    settings = Mock()
    settings.minio_endpoint = "localhost:9000"
    settings.minio_access_key = "minioadmin"
    settings.minio_secret_key = "minioadmin"
    settings.minio_secure = False
    settings.storage_external_url = "https://storage.example.com"
    return settings


# ===== upload_recording 테스트 (3개) =====


def test_upload_recording_success(storage_service, mock_minio_client, mock_settings):
    """녹음 바이트 데이터 업로드 성공"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        meeting_id = "meeting-123"
        user_id = "user-456"
        timestamp = "20260108_120000"
        data = b"fake audio data"

        result = storage_service.upload_recording(
            meeting_id=meeting_id,
            user_id=user_id,
            timestamp=timestamp,
            data=data,
        )

        # 경로 형식 검증
        expected_path = f"{meeting_id}/{user_id}_{timestamp}.webm"
        assert result == expected_path

        # put_object 호출 확인
        mock_minio_client.put_object.assert_called_once()
        call_args = mock_minio_client.put_object.call_args
        assert call_args.kwargs["bucket_name"] == "recordings"
        assert call_args.kwargs["object_name"] == expected_path
        assert call_args.kwargs["length"] == len(data)
        assert call_args.kwargs["content_type"] == "audio/webm"


def test_upload_recording_path_format(storage_service, mock_minio_client, mock_settings):
    """업로드 경로 형식이 올바른지 검증"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        result = storage_service.upload_recording(
            meeting_id="abc-def-ghi",
            user_id="user-xyz",
            timestamp="20260108_153045",
            data=b"test",
        )

        assert result == "abc-def-ghi/user-xyz_20260108_153045.webm"


def test_upload_recording_content_type(storage_service, mock_minio_client, mock_settings):
    """콘텐츠 타입이 audio/webm으로 설정되는지 확인"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        storage_service.upload_recording(
            meeting_id="test",
            user_id="user",
            timestamp="20260108_120000",
            data=b"data",
        )

        call_args = mock_minio_client.put_object.call_args
        assert call_args.kwargs["content_type"] == "audio/webm"


# ===== upload_recording_file 테스트 (2개) =====


def test_upload_recording_file_success(storage_service, mock_minio_client, mock_settings):
    """파일 경로로 녹음 업로드 성공"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        meeting_id = "meeting-789"
        user_id = "user-123"
        timestamp = "20260108_140000"
        file_path = "/tmp/recording.webm"

        result = storage_service.upload_recording_file(
            meeting_id=meeting_id,
            user_id=user_id,
            timestamp=timestamp,
            file_path=file_path,
        )

        expected_path = f"{meeting_id}/{user_id}_{timestamp}.webm"
        assert result == expected_path

        # fput_object 호출 확인
        mock_minio_client.fput_object.assert_called_once_with(
            bucket_name="recordings",
            object_name=expected_path,
            file_path=file_path,
            content_type="audio/webm",
        )


def test_upload_recording_file_error(storage_service, mock_minio_client, mock_settings):
    """파일 업로드 실패 시 예외 발생"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client
        mock_minio_client.fput_object.side_effect = S3Error(
            code="InternalError",
            message="Upload failed",
            resource="/test",
            request_id="req-123",
            host_id="host-456",
            response=Mock(),
        )

        with pytest.raises(S3Error):
            storage_service.upload_recording_file(
                meeting_id="test",
                user_id="user",
                timestamp="20260108_120000",
                file_path="/tmp/test.webm",
            )


# ===== get_recording_upload_url 테스트 (3개) =====


def test_get_recording_upload_url_success(storage_service, mock_minio_client, mock_settings):
    """녹음 업로드 URL 생성 성공"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        meeting_id = "meeting-abc"
        user_id = "user-def"
        timestamp = "20260108_150000"

        url, file_path = storage_service.get_recording_upload_url(
            meeting_id=meeting_id,
            user_id=user_id,
            timestamp=timestamp,
        )

        # 파일 경로 검증
        expected_path = f"{meeting_id}/{user_id}_{timestamp}.webm"
        assert file_path == expected_path

        # URL이 외부 URL로 변환되었는지 확인
        assert "storage.example.com" in url
        assert "localhost:9000" not in url


def test_get_recording_upload_url_returns_tuple(storage_service, mock_minio_client, mock_settings):
    """반환값이 (url, file_path) 튜플인지 확인"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        result = storage_service.get_recording_upload_url(
            meeting_id="test",
            user_id="user",
            timestamp="20260108_120000",
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        url, file_path = result
        assert isinstance(url, str)
        assert isinstance(file_path, str)
        assert file_path.endswith(".webm")


def test_get_recording_upload_url_with_expiry(storage_service, mock_minio_client, mock_settings):
    """만료 시간을 지정한 URL 생성"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        custom_expiry = timedelta(hours=2)
        storage_service.get_recording_upload_url(
            meeting_id="test",
            user_id="user",
            timestamp="20260108_120000",
            expires=custom_expiry,
        )

        # presigned_put_object가 올바른 expires로 호출되었는지 확인
        call_args = mock_minio_client.presigned_put_object.call_args
        assert call_args.kwargs["expires"] == custom_expiry


# ===== check_file_exists 테스트 (3개) =====


def test_check_file_exists_true(storage_service, mock_minio_client, mock_settings):
    """파일이 존재하면 True 반환"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        result = storage_service.check_file_exists(
            bucket="recordings",
            object_name="test/file.webm",
        )

        assert result is True
        mock_minio_client.stat_object.assert_called_once_with(
            bucket_name="recordings",
            object_name="test/file.webm",
        )


def test_check_file_exists_false(storage_service, mock_minio_client, mock_settings):
    """파일이 없으면 False 반환"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client
        mock_minio_client.stat_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            resource="/test",
            request_id="req-123",
            host_id="host-456",
            response=Mock(),
        )

        result = storage_service.check_file_exists(
            bucket="recordings",
            object_name="nonexistent.webm",
        )

        assert result is False


def test_check_file_exists_error(storage_service, mock_minio_client, mock_settings):
    """다른 S3 에러는 예외 발생"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client
        mock_minio_client.stat_object.side_effect = S3Error(
            code="InternalError",
            message="Server error",
            resource="/test",
            request_id="req-123",
            host_id="host-456",
            response=Mock(),
        )

        with pytest.raises(S3Error):
            storage_service.check_file_exists("recordings", "test.webm")


# ===== get_file_info 테스트 (3개) =====


def test_get_file_info_success(storage_service, mock_minio_client, mock_settings):
    """파일 정보 조회 성공"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        info = storage_service.get_file_info(
            bucket="recordings",
            object_name="test/file.webm",
        )

        assert info is not None
        assert info["size"] == 1024 * 1024
        assert info["content_type"] == "audio/webm"
        assert info["etag"] == "test-etag"
        assert "last_modified" in info


def test_get_file_info_not_found(storage_service, mock_minio_client, mock_settings):
    """파일이 없으면 None 반환"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client
        mock_minio_client.stat_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            resource="/test",
            request_id="req-123",
            host_id="host-456",
            response=Mock(),
        )

        info = storage_service.get_file_info("recordings", "nonexistent.webm")

        assert info is None


def test_get_file_info_error(storage_service, mock_minio_client, mock_settings):
    """다른 S3 에러는 예외 발생"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client
        mock_minio_client.stat_object.side_effect = S3Error(
            code="AccessDenied",
            message="Access denied",
            resource="/test",
            request_id="req-123",
            host_id="host-456",
            response=Mock(),
        )

        with pytest.raises(S3Error):
            storage_service.get_file_info("recordings", "test.webm")


# ===== get_recording_url 테스트 (2개) =====


def test_get_recording_url_success(storage_service, mock_minio_client, mock_settings):
    """녹음 다운로드 URL 생성 성공"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        file_path = "meeting-123/user-456_20260108_120000.webm"
        url = storage_service.get_recording_url(file_path)

        assert url == "https://minio.test/presigned-get-url"
        mock_minio_client.presigned_get_object.assert_called_once_with(
            bucket_name="recordings",
            object_name=file_path,
            expires=timedelta(hours=1),
        )


def test_get_recording_url_with_expiry(storage_service, mock_minio_client, mock_settings):
    """만료 시간을 지정한 다운로드 URL 생성"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        custom_expiry = timedelta(minutes=30)
        storage_service.get_recording_url(
            file_path="test.webm",
            expires=custom_expiry,
        )

        call_args = mock_minio_client.presigned_get_object.call_args
        assert call_args.kwargs["expires"] == custom_expiry


# ===== get_recording_file 테스트 (2개) =====


def test_get_recording_file_success(storage_service, mock_minio_client, mock_settings):
    """녹음 파일 다운로드 성공"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        file_path = "meeting-123/recording.webm"
        data = storage_service.get_recording_file(file_path)

        assert data == b"test file content"
        mock_minio_client.get_object.assert_called_once_with(
            bucket_name="recordings",
            object_name=file_path,
        )


def test_get_recording_file_error(storage_service, mock_minio_client, mock_settings):
    """파일 다운로드 실패 시 예외 발생"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client
        mock_minio_client.get_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            resource="/test",
            request_id="req-123",
            host_id="host-456",
            response=Mock(),
        )

        with pytest.raises(S3Error):
            storage_service.get_recording_file("nonexistent.webm")


# ===== delete_recording 테스트 (2개) =====


def test_delete_recording_success(storage_service, mock_minio_client, mock_settings):
    """녹음 파일 삭제 성공"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client

        file_path = "meeting-123/recording.webm"
        storage_service.delete_recording(file_path)

        mock_minio_client.remove_object.assert_called_once_with(
            "recordings",
            file_path,
        )


def test_delete_recording_error(storage_service, mock_minio_client, mock_settings):
    """파일 삭제 실패 시 예외 발생"""
    with patch("app.core.storage.get_settings", return_value=mock_settings):
        storage_service._client = mock_minio_client
        mock_minio_client.remove_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            resource="/test",
            request_id="req-123",
            host_id="host-456",
            response=Mock(),
        )

        with pytest.raises(S3Error):
            storage_service.delete_recording("nonexistent.webm")
