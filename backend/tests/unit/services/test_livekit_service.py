"""LiveKit 서비스 단위 테스트

테스트 케이스:
- 토큰 생성: 성공, LiveKit 미설정, 호스트 권한
- Egress 상태 관리 (Redis): 설정/조회, 삭제, TTL
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.livekit_service import (
    EGRESS_KEY_PREFIX,
    EGRESS_TTL_SECONDS,
    LiveKitService,
)


# ===== 토큰 생성 테스트 =====


def test_generate_token_success():
    """토큰 생성 성공 테스트"""
    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://localhost:7880",
            livekit_external_url="ws://localhost:7880",
        )

        service = LiveKitService()
        token = service.generate_token(
            room_name="meeting-test-123",
            participant_id="user-1",
            participant_name="Test User",
            is_host=False,
            ttl_seconds=3600,
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0


def test_generate_token_not_configured():
    """LiveKit 미설정 시 토큰 생성 실패"""
    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="",
            livekit_api_secret="",
            livekit_ws_url="",
            livekit_external_url="",
        )

        service = LiveKitService()

        with pytest.raises(ValueError, match="LiveKit is not configured"):
            service.generate_token(
                room_name="meeting-test-123",
                participant_id="user-1",
                participant_name="Test User",
            )


def test_generate_token_with_host_permissions():
    """호스트 권한 토큰 생성 테스트"""
    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://localhost:7880",
            livekit_external_url="ws://localhost:7880",
        )

        service = LiveKitService()
        token = service.generate_token(
            room_name="meeting-test-123",
            participant_id="host-user",
            participant_name="Host User",
            is_host=True,
            ttl_seconds=3600,
        )

        # 토큰이 생성되는지 확인
        # 실제 JWT 페이로드 검증은 통합 테스트에서 수행
        assert token is not None
        assert isinstance(token, str)


# ===== Egress 상태 관리 테스트 (Redis Mock) =====


@pytest.mark.asyncio
async def test_set_and_get_active_egress():
    """활성 egress 설정 및 조회 테스트"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "egress-123"
    mock_redis.set.return_value = True

    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://localhost:7880",
            livekit_external_url="ws://localhost:7880",
        )

        service = LiveKitService()

        with patch("app.services.livekit_service.get_redis", return_value=mock_redis):
            meeting_id = uuid4()
            egress_id = "egress-123"

            # 설정
            await service._set_active_egress(meeting_id, egress_id)
            mock_redis.set.assert_called_once_with(
                f"{EGRESS_KEY_PREFIX}{meeting_id}",
                egress_id,
                ex=EGRESS_TTL_SECONDS,
            )

            # 조회
            result = await service._get_active_egress(meeting_id)
            assert result == egress_id
            mock_redis.get.assert_called_once_with(f"{EGRESS_KEY_PREFIX}{meeting_id}")


@pytest.mark.asyncio
async def test_clear_active_egress():
    """활성 egress 삭제 테스트"""
    mock_redis = AsyncMock()
    mock_redis.delete.return_value = 1

    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://localhost:7880",
            livekit_external_url="ws://localhost:7880",
        )

        service = LiveKitService()

        with patch("app.services.livekit_service.get_redis", return_value=mock_redis):
            meeting_id = uuid4()

            # 삭제
            await service._clear_active_egress(meeting_id)
            mock_redis.delete.assert_called_once_with(f"{EGRESS_KEY_PREFIX}{meeting_id}")


@pytest.mark.asyncio
async def test_clear_active_egress_public_method():
    """공개 clear_active_egress 메서드 테스트"""
    mock_redis = AsyncMock()
    mock_redis.delete.return_value = 1

    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://localhost:7880",
            livekit_external_url="ws://localhost:7880",
        )

        service = LiveKitService()

        with patch("app.services.livekit_service.get_redis", return_value=mock_redis):
            meeting_id = uuid4()

            # 공개 메서드 호출
            await service.clear_active_egress(meeting_id)
            mock_redis.delete.assert_called_once_with(f"{EGRESS_KEY_PREFIX}{meeting_id}")


# ===== is_configured 프로퍼티 테스트 =====


def test_is_configured_true():
    """LiveKit 설정 완료 여부 - True"""
    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://localhost:7880",
            livekit_external_url="ws://localhost:7880",
        )

        service = LiveKitService()
        assert service.is_configured is True


def test_is_configured_false():
    """LiveKit 설정 완료 여부 - False (API key 누락)"""
    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://localhost:7880",
            livekit_external_url="ws://localhost:7880",
        )

        service = LiveKitService()
        assert service.is_configured is False


# ===== get_room_name 테스트 =====


def test_get_room_name():
    """룸 이름 생성 테스트"""
    meeting_id = uuid4()
    room_name = LiveKitService.get_room_name(meeting_id)
    assert room_name == f"meeting-{meeting_id}"


# ===== get_ws_url_for_client 테스트 =====


def test_get_ws_url_for_client():
    """클라이언트용 WebSocket URL 반환 테스트"""
    with patch("app.services.livekit_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
            livekit_ws_url="ws://internal:7880",
            livekit_external_url="wss://external.example.com",
        )

        service = LiveKitService()
        assert service.get_ws_url_for_client() == "wss://external.example.com"
