"""WebSocket 메시지 핸들러 단위 테스트

총 18개 테스트:
- JoinHandler: 2개 (참여자 목록 전송, 다른 참여자에게 알림)
- OfferAnswerHandler: 3개 (offer 전송, answer 전송, 데이터 누락)
- ICECandidateHandler: 4개 (특정 사용자, 브로드캐스트, candidate 누락, screen ice warning)
- MuteHandler: 2개 (mute, unmute)
- ScreenShareHandler: 2개 (start, stop)
- ScreenOfferAnswerHandler: 2개 (성공, 데이터 누락)
- dispatch_message: 3개 (LEAVE, 알려진 타입, 알 수 없는 타입)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.handlers.websocket_message_handlers import (
    JoinHandler,
    OfferAnswerHandler,
    ICECandidateHandler,
    MuteHandler,
    ScreenShareHandler,
    ScreenOfferAnswerHandler,
    dispatch_message,
    HANDLERS,
)
from app.schemas.webrtc import SignalingMessageType


# ===== Test Fixtures =====


@pytest.fixture
def mock_connection_manager():
    """connection_manager mock"""
    with patch("app.handlers.websocket_message_handlers.connection_manager") as mock:
        mock.send_to_user = AsyncMock()
        mock.broadcast = AsyncMock()
        mock.get_participants = MagicMock(return_value=[])
        mock.get_participant = MagicMock(return_value=None)
        mock.update_mute_status = MagicMock()
        yield mock


@pytest.fixture
def sample_participant():
    """샘플 참여자 객체"""
    participant = MagicMock()
    participant.user_id = uuid4()
    participant.user_name = "Test User"
    participant.role = "host"
    participant.audio_muted = False
    return participant


# ===== JoinHandler 테스트 (2개) =====


@pytest.mark.asyncio
async def test_join_handler_sends_participants_list(mock_connection_manager, sample_participant):
    """JOIN 시 현재 참여자 목록 전송"""
    mock_connection_manager.get_participants.return_value = [sample_participant]

    handler = JoinHandler()
    meeting_id = uuid4()
    user_id = uuid4()

    await handler.handle(meeting_id, user_id, {})

    # 참여자에게 JOINED 메시지 전송 확인
    mock_connection_manager.send_to_user.assert_called_once()
    call_args = mock_connection_manager.send_to_user.call_args
    assert call_args[0][0] == meeting_id
    assert call_args[0][1] == user_id
    assert call_args[0][2]["type"] == SignalingMessageType.JOINED
    assert "participants" in call_args[0][2]


@pytest.mark.asyncio
async def test_join_handler_broadcasts_to_others(mock_connection_manager, sample_participant):
    """JOIN 시 다른 참여자들에게 알림"""
    user_id = uuid4()
    sample_participant.user_id = user_id
    mock_connection_manager.get_participant.return_value = sample_participant

    handler = JoinHandler()
    meeting_id = uuid4()

    await handler.handle(meeting_id, user_id, {})

    # 브로드캐스트 확인
    mock_connection_manager.broadcast.assert_called_once()
    call_args = mock_connection_manager.broadcast.call_args
    assert call_args[0][0] == meeting_id
    assert call_args[0][1]["type"] == SignalingMessageType.PARTICIPANT_JOINED
    assert call_args[1]["exclude_user_id"] == user_id


# ===== OfferAnswerHandler 테스트 (3개) =====


@pytest.mark.asyncio
async def test_offer_handler_sends_offer(mock_connection_manager):
    """OFFER 메시지 전송"""
    handler = OfferAnswerHandler(SignalingMessageType.OFFER)
    meeting_id = uuid4()
    user_id = uuid4()
    target_id = uuid4()

    data = {
        "targetUserId": str(target_id),
        "sdp": {"type": "offer", "sdp": "v=0..."},
    }

    await handler.handle(meeting_id, user_id, data)

    mock_connection_manager.send_to_user.assert_called_once()
    call_args = mock_connection_manager.send_to_user.call_args
    assert call_args[0][1] == target_id
    assert call_args[0][2]["type"] == SignalingMessageType.OFFER
    assert call_args[0][2]["fromUserId"] == str(user_id)


@pytest.mark.asyncio
async def test_answer_handler_sends_answer(mock_connection_manager):
    """ANSWER 메시지 전송"""
    handler = OfferAnswerHandler(SignalingMessageType.ANSWER)
    meeting_id = uuid4()
    user_id = uuid4()
    target_id = uuid4()

    data = {
        "targetUserId": str(target_id),
        "sdp": {"type": "answer", "sdp": "v=0..."},
    }

    await handler.handle(meeting_id, user_id, data)

    mock_connection_manager.send_to_user.assert_called_once()
    call_args = mock_connection_manager.send_to_user.call_args
    assert call_args[0][2]["type"] == SignalingMessageType.ANSWER


@pytest.mark.asyncio
async def test_offer_answer_handler_missing_data(mock_connection_manager):
    """데이터 누락 시 아무 동작 안 함"""
    handler = OfferAnswerHandler(SignalingMessageType.OFFER)
    meeting_id = uuid4()
    user_id = uuid4()

    # targetUserId 없음
    await handler.handle(meeting_id, user_id, {"sdp": "test"})
    mock_connection_manager.send_to_user.assert_not_called()

    # sdp 없음
    await handler.handle(meeting_id, user_id, {"targetUserId": str(uuid4())})
    mock_connection_manager.send_to_user.assert_not_called()


# ===== ICECandidateHandler 테스트 (4개) =====


@pytest.mark.asyncio
async def test_ice_candidate_to_specific_user(mock_connection_manager):
    """ICE candidate를 특정 사용자에게 전송"""
    handler = ICECandidateHandler(SignalingMessageType.ICE_CANDIDATE)
    meeting_id = uuid4()
    user_id = uuid4()
    target_id = uuid4()

    data = {
        "targetUserId": str(target_id),
        "candidate": {"candidate": "candidate:..."},
    }

    await handler.handle(meeting_id, user_id, data)

    mock_connection_manager.send_to_user.assert_called_once()
    call_args = mock_connection_manager.send_to_user.call_args
    assert call_args[0][1] == target_id
    assert call_args[0][2]["type"] == SignalingMessageType.ICE_CANDIDATE


@pytest.mark.asyncio
async def test_ice_candidate_broadcast(mock_connection_manager):
    """ICE candidate를 모든 사용자에게 브로드캐스트"""
    handler = ICECandidateHandler(SignalingMessageType.ICE_CANDIDATE)
    meeting_id = uuid4()
    user_id = uuid4()

    data = {
        "candidate": {"candidate": "candidate:..."},
        # targetUserId 없음 - 브로드캐스트
    }

    await handler.handle(meeting_id, user_id, data)

    mock_connection_manager.broadcast.assert_called_once()
    call_args = mock_connection_manager.broadcast.call_args
    # broadcast(meeting_id, message, exclude_user_id=user_id)
    assert call_args[0][1]["type"] == SignalingMessageType.ICE_CANDIDATE
    assert call_args.kwargs["exclude_user_id"] == user_id


@pytest.mark.asyncio
async def test_ice_candidate_missing_candidate(mock_connection_manager):
    """candidate 누락 시 아무 동작 안 함"""
    handler = ICECandidateHandler(SignalingMessageType.ICE_CANDIDATE)
    meeting_id = uuid4()
    user_id = uuid4()

    await handler.handle(meeting_id, user_id, {})

    mock_connection_manager.send_to_user.assert_not_called()
    mock_connection_manager.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_screen_ice_candidate_no_target_logs_warning(mock_connection_manager):
    """Screen ICE candidate에 targetUserId 없으면 경고 로그"""
    handler = ICECandidateHandler(SignalingMessageType.SCREEN_ICE_CANDIDATE)
    meeting_id = uuid4()
    user_id = uuid4()

    data = {
        "candidate": {"candidate": "candidate:..."},
        # targetUserId 없음
    }

    with patch("app.handlers.websocket_message_handlers.logger") as mock_logger:
        await handler.handle(meeting_id, user_id, data)

        mock_logger.warning.assert_called_once()
        assert "missing targetUserId" in mock_logger.warning.call_args[0][0]


# ===== MuteHandler 테스트 (2개) =====


@pytest.mark.asyncio
async def test_mute_handler_mute(mock_connection_manager):
    """MUTE 처리 - muted=True"""
    handler = MuteHandler()
    meeting_id = uuid4()
    user_id = uuid4()

    await handler.handle(meeting_id, user_id, {"muted": True})

    mock_connection_manager.update_mute_status.assert_called_once_with(
        meeting_id, user_id, True
    )
    mock_connection_manager.broadcast.assert_called_once()
    call_args = mock_connection_manager.broadcast.call_args
    assert call_args[0][1]["type"] == SignalingMessageType.PARTICIPANT_MUTED
    assert call_args[0][1]["muted"] is True


@pytest.mark.asyncio
async def test_mute_handler_unmute(mock_connection_manager):
    """MUTE 처리 - muted=False (unmute)"""
    handler = MuteHandler()
    meeting_id = uuid4()
    user_id = uuid4()

    await handler.handle(meeting_id, user_id, {"muted": False})

    mock_connection_manager.update_mute_status.assert_called_once_with(
        meeting_id, user_id, False
    )


# ===== ScreenShareHandler 테스트 (2개) =====


@pytest.mark.asyncio
async def test_screen_share_start(mock_connection_manager):
    """화면공유 시작"""
    handler = ScreenShareHandler("start")
    meeting_id = uuid4()
    user_id = uuid4()

    await handler.handle(meeting_id, user_id, {})

    mock_connection_manager.broadcast.assert_called_once()
    call_args = mock_connection_manager.broadcast.call_args
    assert call_args[0][1]["type"] == SignalingMessageType.SCREEN_SHARE_STARTED
    assert call_args[0][1]["userId"] == str(user_id)


@pytest.mark.asyncio
async def test_screen_share_stop(mock_connection_manager):
    """화면공유 중지"""
    handler = ScreenShareHandler("stop")
    meeting_id = uuid4()
    user_id = uuid4()

    await handler.handle(meeting_id, user_id, {})

    mock_connection_manager.broadcast.assert_called_once()
    call_args = mock_connection_manager.broadcast.call_args
    assert call_args[0][1]["type"] == SignalingMessageType.SCREEN_SHARE_STOPPED


# ===== ScreenOfferAnswerHandler 테스트 (2개) =====


@pytest.mark.asyncio
async def test_screen_offer_handler(mock_connection_manager):
    """SCREEN_OFFER 전송"""
    handler = ScreenOfferAnswerHandler(SignalingMessageType.SCREEN_OFFER)
    meeting_id = uuid4()
    user_id = uuid4()
    target_id = uuid4()

    data = {
        "targetUserId": str(target_id),
        "sdp": {"type": "offer", "sdp": "v=0..."},
    }

    await handler.handle(meeting_id, user_id, data)

    mock_connection_manager.send_to_user.assert_called_once()
    call_args = mock_connection_manager.send_to_user.call_args
    assert call_args[0][2]["type"] == SignalingMessageType.SCREEN_OFFER


@pytest.mark.asyncio
async def test_screen_offer_answer_missing_data(mock_connection_manager):
    """데이터 누락 시 경고 로그"""
    handler = ScreenOfferAnswerHandler(SignalingMessageType.SCREEN_OFFER)
    meeting_id = uuid4()
    user_id = uuid4()

    with patch("app.handlers.websocket_message_handlers.logger") as mock_logger:
        await handler.handle(meeting_id, user_id, {"sdp": "test"})

        mock_logger.warning.assert_called_once()
        mock_connection_manager.send_to_user.assert_not_called()


# ===== dispatch_message 테스트 (3개) =====


@pytest.mark.asyncio
async def test_dispatch_message_leave_returns_false(mock_connection_manager):
    """LEAVE 메시지는 False 반환"""
    meeting_id = uuid4()
    user_id = uuid4()

    result = await dispatch_message(
        SignalingMessageType.LEAVE, meeting_id, user_id, {}
    )

    assert result is False


@pytest.mark.asyncio
async def test_dispatch_message_known_type(mock_connection_manager):
    """알려진 메시지 타입은 핸들러 호출 후 True 반환"""
    meeting_id = uuid4()
    user_id = uuid4()

    result = await dispatch_message(
        SignalingMessageType.MUTE, meeting_id, user_id, {"muted": True}
    )

    assert result is True
    mock_connection_manager.update_mute_status.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_message_unknown_type(mock_connection_manager):
    """알 수 없는 메시지 타입은 경고 로그 후 True 반환"""
    meeting_id = uuid4()
    user_id = uuid4()

    with patch("app.handlers.websocket_message_handlers.logger") as mock_logger:
        result = await dispatch_message(
            "unknown-type", meeting_id, user_id, {}
        )

        assert result is True
        mock_logger.warning.assert_called_once()
        assert "Unknown message type" in mock_logger.warning.call_args[0][0]


# ===== HANDLERS 레지스트리 테스트 =====


def test_handlers_registry_complete():
    """모든 핸들러가 레지스트리에 등록되어 있는지 확인"""
    expected_handlers = [
        SignalingMessageType.JOIN,
        SignalingMessageType.OFFER,
        SignalingMessageType.ANSWER,
        SignalingMessageType.ICE_CANDIDATE,
        SignalingMessageType.MUTE,
        SignalingMessageType.SCREEN_SHARE_START,
        SignalingMessageType.SCREEN_SHARE_STOP,
        SignalingMessageType.SCREEN_OFFER,
        SignalingMessageType.SCREEN_ANSWER,
        SignalingMessageType.SCREEN_ICE_CANDIDATE,
    ]

    for msg_type in expected_handlers:
        assert msg_type in HANDLERS, f"{msg_type} not in HANDLERS"
