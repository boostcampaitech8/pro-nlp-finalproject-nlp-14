"""ChatMessageHandler 단위 테스트"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.handlers.websocket_message_handlers import ChatMessageHandler


class TestChatMessageHandler:
    """ChatMessageHandler 테스트"""

    @pytest.fixture
    def mock_chat_service(self):
        """Mock ChatService"""
        service = MagicMock()
        service.create_message = AsyncMock()
        return service

    @pytest.fixture
    def handler(self, mock_chat_service):
        """ChatMessageHandler 인스턴스"""
        return ChatMessageHandler(chat_service=mock_chat_service)

    @pytest.mark.asyncio
    async def test_handle_chat_message(self, handler, mock_chat_service):
        """채팅 메시지 처리 테스트"""
        meeting_id = uuid4()
        user_id = uuid4()
        content = "안녕하세요!"

        # Mock 메시지 객체
        mock_message = MagicMock()
        mock_message.id = uuid4()
        mock_message.content = content
        mock_message.created_at = datetime(2026, 1, 10, 15, 0, 0, tzinfo=timezone.utc)
        mock_chat_service.create_message.return_value = mock_message

        with patch(
            "app.handlers.websocket_message_handlers.connection_manager"
        ) as mock_cm:
            mock_cm.broadcast = AsyncMock()
            mock_cm.get_participant = MagicMock(
                return_value=MagicMock(user_name="테스트 사용자")
            )

            await handler.handle(meeting_id, user_id, {"content": content})

            # 메시지 생성 확인
            mock_chat_service.create_message.assert_called_once_with(
                meeting_id=meeting_id,
                user_id=user_id,
                content=content,
            )

            # 브로드캐스트 확인
            mock_cm.broadcast.assert_called_once()
            call_args = mock_cm.broadcast.call_args
            assert call_args[0][0] == meeting_id
            assert call_args[0][1]["type"] == "chat-message"
            assert call_args[0][1]["content"] == content
            assert call_args[0][1]["userId"] == str(user_id)

    @pytest.mark.asyncio
    async def test_handle_empty_message_ignored(self, handler, mock_chat_service):
        """빈 메시지는 무시됨 테스트"""
        meeting_id = uuid4()
        user_id = uuid4()

        with patch(
            "app.handlers.websocket_message_handlers.connection_manager"
        ) as mock_cm:
            mock_cm.broadcast = AsyncMock()

            # 빈 메시지
            await handler.handle(meeting_id, user_id, {"content": ""})
            mock_chat_service.create_message.assert_not_called()
            mock_cm.broadcast.assert_not_called()

            # 공백만 있는 메시지
            await handler.handle(meeting_id, user_id, {"content": "   "})
            mock_chat_service.create_message.assert_not_called()
            mock_cm.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_missing_content(self, handler, mock_chat_service):
        """content가 없는 메시지 무시 테스트"""
        meeting_id = uuid4()
        user_id = uuid4()

        with patch(
            "app.handlers.websocket_message_handlers.connection_manager"
        ) as mock_cm:
            mock_cm.broadcast = AsyncMock()

            await handler.handle(meeting_id, user_id, {})
            mock_chat_service.create_message.assert_not_called()
            mock_cm.broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_includes_user_info(self, handler, mock_chat_service):
        """브로드캐스트에 사용자 정보 포함 테스트"""
        meeting_id = uuid4()
        user_id = uuid4()
        user_name = "홍길동"

        mock_message = MagicMock()
        mock_message.id = uuid4()
        mock_message.content = "테스트"
        mock_message.created_at = datetime(2026, 1, 10, 15, 0, 0, tzinfo=timezone.utc)
        mock_chat_service.create_message.return_value = mock_message

        with patch(
            "app.handlers.websocket_message_handlers.connection_manager"
        ) as mock_cm:
            mock_cm.broadcast = AsyncMock()
            mock_cm.get_participant = MagicMock(
                return_value=MagicMock(user_name=user_name)
            )

            await handler.handle(meeting_id, user_id, {"content": "테스트"})

            call_args = mock_cm.broadcast.call_args
            broadcast_data = call_args[0][1]
            assert broadcast_data["userName"] == user_name
            assert broadcast_data["messageId"] == str(mock_message.id)
