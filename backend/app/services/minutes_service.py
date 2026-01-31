"""Minutes 서비스

Minutes View 조회 (중첩 구조: agendas → decisions → suggestions/comments)
"""

import logging

from app.repositories.kg.repository import KGRepository
from app.schemas.minutes import MinutesResponse
from neo4j import AsyncDriver

logger = logging.getLogger(__name__)


class MinutesService:
    """Minutes 서비스"""

    def __init__(self, driver: AsyncDriver):
        self.kg_repo = KGRepository(driver)

    async def get_minutes(self, meeting_id: str) -> MinutesResponse:
        """Minutes View 조회 (중첩 구조)

        Returns:
            MinutesResponse with nested structure:
            - meeting_id
            - summary
            - agendas[].decisions[].suggestions[]
            - agendas[].decisions[].comments[].replies[]
            - action_items[]
        """
        data = await self.kg_repo.get_minutes_view(meeting_id)

        if not data:
            raise ValueError("MEETING_NOT_FOUND")

        logger.info(f"Minutes retrieved: meeting={meeting_id}")

        return MinutesResponse(**data)
