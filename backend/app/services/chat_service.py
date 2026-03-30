"""채팅 서비스"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatMessage


class ChatService:
    """채팅 메시지 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_message(
        self, meeting_id: UUID, user_id: UUID, content: str
    ) -> ChatMessage:
        """채팅 메시지 생성

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            content: 메시지 내용

        Returns:
            생성된 ChatMessage

        Raises:
            ValueError: 빈 메시지인 경우
        """
        # 공백 제거
        content = content.strip()

        if not content:
            raise ValueError("Message content cannot be empty")

        message = ChatMessage(
            meeting_id=meeting_id,
            user_id=user_id,
            content=content,
        )

        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def get_messages(
        self, meeting_id: UUID, page: int = 1, limit: int = 50
    ) -> list[ChatMessage]:
        """채팅 메시지 목록 조회 (최신순)

        Args:
            meeting_id: 회의 ID
            page: 페이지 번호 (1부터 시작)
            limit: 페이지당 메시지 수

        Returns:
            ChatMessage 목록
        """
        offset = (page - 1) * limit

        query = (
            select(ChatMessage)
            .options(selectinload(ChatMessage.user))
            .where(ChatMessage.meeting_id == meeting_id)
            .order_by(ChatMessage.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_message_count(self, meeting_id: UUID) -> int:
        """회의의 채팅 메시지 총 개수

        Args:
            meeting_id: 회의 ID

        Returns:
            메시지 개수
        """
        query = select(func.count(ChatMessage.id)).where(
            ChatMessage.meeting_id == meeting_id
        )

        result = await self.db.execute(query)
        return result.scalar() or 0
