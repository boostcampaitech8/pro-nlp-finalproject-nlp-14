"""LiveKit 웹훅 API 단위 테스트

테스트 케이스:
- 웹훅 서명 검증: Authorization 헤더 누락, 유효하지 않은 서명, 유효한 서명
- 이벤트 처리: egress_ended (성공/실패), participant_joined, room_finished
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.api.v1.endpoints.livekit_webhooks import verify_and_parse_webhook
from app.main import app


# ===== 웹훅 서명 검증 테스트 =====


@pytest.mark.asyncio
async def test_webhook_missing_authorization():
    """Authorization 헤더 누락 시 None 반환"""
    mock_request = MagicMock()
    mock_request.body = AsyncMock(return_value=b'{"event": "test"}')

    result = await verify_and_parse_webhook(mock_request, authorization=None)

    assert result is None


@pytest.mark.asyncio
async def test_webhook_livekit_not_configured():
    """LiveKit 미설정 시 None 반환"""
    mock_request = MagicMock()
    mock_request.body = AsyncMock(return_value=b'{"event": "test"}')

    with patch("app.api.v1.endpoints.livekit_webhooks.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="",
            livekit_api_secret="",
        )

        result = await verify_and_parse_webhook(
            mock_request, authorization="Bearer test-token"
        )

        assert result is None


@pytest.mark.asyncio
async def test_webhook_invalid_signature():
    """유효하지 않은 서명 시 None 반환"""
    mock_request = MagicMock()
    mock_request.body = AsyncMock(return_value=b'{"event": "test"}')

    with patch("app.api.v1.endpoints.livekit_webhooks.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
        )

        # TokenVerifier와 WebhookReceiver 모두 모킹
        with patch("app.api.v1.endpoints.livekit_webhooks.api.TokenVerifier"):
            with patch("app.api.v1.endpoints.livekit_webhooks.api.WebhookReceiver") as mock_receiver:
                mock_receiver.return_value.receive.side_effect = Exception("Invalid signature")

                result = await verify_and_parse_webhook(
                    mock_request, authorization="Bearer invalid-token"
                )

                assert result is None


@pytest.mark.asyncio
async def test_webhook_valid_signature():
    """유효한 서명 시 이벤트 반환"""
    mock_request = MagicMock()
    mock_request.body = AsyncMock(return_value=b'{"event": "participant_joined"}')

    # Mock WebhookEvent
    mock_event = MagicMock()
    mock_event.event = "participant_joined"

    with patch("app.api.v1.endpoints.livekit_webhooks.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            livekit_api_key="test-api-key",
            livekit_api_secret="test-api-secret",
        )

        # TokenVerifier와 WebhookReceiver 모두 모킹
        with patch("app.api.v1.endpoints.livekit_webhooks.api.TokenVerifier"):
            with patch("app.api.v1.endpoints.livekit_webhooks.api.WebhookReceiver") as mock_receiver:
                mock_receiver.return_value.receive.return_value = mock_event

                # MessageToDict는 함수 내부에서 import되므로 google.protobuf.json_format에서 패치
                with patch("google.protobuf.json_format.MessageToDict") as mock_to_dict:
                    mock_to_dict.return_value = {"event": "participant_joined"}

                    result = await verify_and_parse_webhook(
                        mock_request, authorization="Bearer valid-token"
                    )

                    assert result is not None
                    assert result["event"] == "participant_joined"


# ===== 웹훅 엔드포인트 통합 테스트 =====


@pytest.mark.asyncio
async def test_webhook_endpoint_returns_401_on_invalid_signature(async_client):
    """유효하지 않은 서명 시 401 반환"""
    with patch(
        "app.api.v1.endpoints.livekit_webhooks.verify_and_parse_webhook",
        return_value=None,
    ):
        response = await async_client.post(
            "/api/v1/livekit/webhook",
            json={"event": "test"},
            headers={"Authorization": "Bearer invalid"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid webhook signature"


@pytest.mark.asyncio
async def test_webhook_endpoint_egress_ended_success(async_client, db_session):
    """egress_ended 이벤트 처리 - 녹음 완료"""
    meeting_id = uuid4()
    egress_id = "egress-123"

    mock_event = {
        "event": "egress_ended",
        "egressInfo": {
            "egressId": egress_id,
            "roomName": f"meeting-{meeting_id}",
            "status": "EGRESS_COMPLETE",
            "fileResults": [
                {
                    "filename": f"meetings/{meeting_id}/composite-12345.ogg",
                    "size": "1048576",
                    "duration": "60000000000",  # 60초 (나노초)
                }
            ],
        },
    }

    with patch(
        "app.api.v1.endpoints.livekit_webhooks.verify_and_parse_webhook",
        return_value=mock_event,
    ):
        with patch(
            "app.api.v1.endpoints.livekit_webhooks.livekit_service.clear_active_egress",
            new_callable=AsyncMock,
        ) as mock_clear:
            response = await async_client.post(
                "/api/v1/livekit/webhook",
                json=mock_event,
                headers={"Authorization": "Bearer valid"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "ok"

            # clear_active_egress가 호출되었는지 확인
            mock_clear.assert_called_once_with(meeting_id)


@pytest.mark.asyncio
async def test_webhook_endpoint_egress_ended_failed(async_client):
    """egress_ended 이벤트 처리 - 녹음 실패"""
    meeting_id = uuid4()

    mock_event = {
        "event": "egress_ended",
        "egressInfo": {
            "egressId": "egress-123",
            "roomName": f"meeting-{meeting_id}",
            "status": "EGRESS_FAILED",
            "error": "Recording failed due to an error",
        },
    }

    with patch(
        "app.api.v1.endpoints.livekit_webhooks.verify_and_parse_webhook",
        return_value=mock_event,
    ):
        with patch(
            "app.api.v1.endpoints.livekit_webhooks.livekit_service.clear_active_egress",
            new_callable=AsyncMock,
        ) as mock_clear:
            response = await async_client.post(
                "/api/v1/livekit/webhook",
                json=mock_event,
                headers={"Authorization": "Bearer valid"},
            )

            assert response.status_code == 200
            # clear_active_egress가 실패 상태에서도 호출되어야 함
            mock_clear.assert_called_once_with(meeting_id)


@pytest.mark.asyncio
async def test_webhook_endpoint_participant_joined(async_client):
    """participant_joined 이벤트 처리"""
    mock_event = {
        "event": "participant_joined",
        "participant": {
            "identity": "user-123",
            "name": "Test User",
        },
        "room": {
            "name": "meeting-test-room",
        },
    }

    with patch(
        "app.api.v1.endpoints.livekit_webhooks.verify_and_parse_webhook",
        return_value=mock_event,
    ):
        response = await async_client.post(
            "/api/v1/livekit/webhook",
            json=mock_event,
            headers={"Authorization": "Bearer valid"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_endpoint_room_finished(async_client):
    """room_finished 이벤트 처리 - VAD 메타데이터 저장"""
    meeting_id = uuid4()

    mock_event = {
        "event": "room_finished",
        "room": {
            "name": f"meeting-{meeting_id}",
        },
    }

    with patch(
        "app.api.v1.endpoints.livekit_webhooks.verify_and_parse_webhook",
        return_value=mock_event,
    ):
        with patch(
            "app.api.v1.endpoints.livekit_webhooks.vad_event_service.store_meeting_vad_metadata",
            new_callable=AsyncMock,
            return_value={"user-1": []},
        ) as mock_vad:
            response = await async_client.post(
                "/api/v1/livekit/webhook",
                json=mock_event,
                headers={"Authorization": "Bearer valid"},
            )

            assert response.status_code == 200
            mock_vad.assert_called_once_with(meeting_id)
