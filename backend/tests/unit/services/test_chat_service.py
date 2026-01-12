"""ChatService 단위 테스트"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_service import ChatService


class TestChatService:
    """ChatService 테스트"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock DB 세션"""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def chat_service(self, mock_db_session):
        """ChatService 인스턴스"""
        return ChatService(mock_db_session)

    @pytest.mark.asyncio
    async def test_create_message(self, chat_service, mock_db_session):
        """메시지 생성 테스트"""
        meeting_id = uuid4()
        user_id = uuid4()
        content = "안녕하세요!"

        # refresh mock: id와 created_at 설정
        async def mock_refresh(obj):
            obj.id = uuid4()
            obj.created_at = "2026-01-10T15:00:00Z"

        mock_db_session.refresh = mock_refresh

        message = await chat_service.create_message(
            meeting_id=meeting_id,
            user_id=user_id,
            content=content,
        )

        # DB에 추가되었는지 확인
        mock_db_session.add.assert_called_once()
        assert message.meeting_id == meeting_id
        assert message.user_id == user_id
        assert message.content == content

    @pytest.mark.asyncio
    async def test_create_message_strips_whitespace(self, chat_service, mock_db_session):
        """메시지 생성 시 공백 제거 테스트"""
        meeting_id = uuid4()
        user_id = uuid4()
        content = "  안녕하세요!  "

        async def mock_refresh(obj):
            obj.id = uuid4()
            obj.created_at = "2026-01-10T15:00:00Z"

        mock_db_session.refresh = mock_refresh

        message = await chat_service.create_message(
            meeting_id=meeting_id,
            user_id=user_id,
            content=content,
        )

        # 앞뒤 공백 제거 확인
        assert message.content == "안녕하세요!"

    @pytest.mark.asyncio
    async def test_create_message_empty_content_raises_error(self, chat_service):
        """빈 메시지 생성 시 에러 테스트"""
        meeting_id = uuid4()
        user_id = uuid4()

        with pytest.raises(ValueError, match="empty"):
            await chat_service.create_message(
                meeting_id=meeting_id,
                user_id=user_id,
                content="",
            )

        with pytest.raises(ValueError, match="empty"):
            await chat_service.create_message(
                meeting_id=meeting_id,
                user_id=user_id,
                content="   ",
            )

    @pytest.mark.asyncio
    async def test_get_messages(self, chat_service, mock_db_session):
        """메시지 목록 조회 테스트"""
        meeting_id = uuid4()

        # Mock 결과 설정
        mock_messages = [
            MagicMock(
                id=uuid4(),
                meeting_id=meeting_id,
                user_id=uuid4(),
                content="메시지 1",
                created_at="2026-01-10T15:00:00Z",
            ),
            MagicMock(
                id=uuid4(),
                meeting_id=meeting_id,
                user_id=uuid4(),
                content="메시지 2",
                created_at="2026-01-10T15:01:00Z",
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        mock_db_session.execute.return_value = mock_result

        messages = await chat_service.get_messages(
            meeting_id=meeting_id,
            page=1,
            limit=10,
        )

        assert len(messages) == 2
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_messages_pagination(self, chat_service, mock_db_session):
        """메시지 페이지네이션 테스트"""
        meeting_id = uuid4()

        mock_messages = [MagicMock() for _ in range(2)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        mock_db_session.execute.return_value = mock_result

        await chat_service.get_messages(
            meeting_id=meeting_id,
            page=2,
            limit=5,
        )

        # execute가 호출되었는지 확인
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_message_count(self, chat_service, mock_db_session):
        """메시지 총 개수 조회 테스트"""
        meeting_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_db_session.execute.return_value = mock_result

        count = await chat_service.get_message_count(meeting_id=meeting_id)

        assert count == 42
        mock_db_session.execute.assert_called_once()
