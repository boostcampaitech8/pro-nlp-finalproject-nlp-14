"""Neo4j 동기화 헬퍼

PostgreSQL -> Neo4j 동기화 래퍼.
동기화 실패 시 로깅만 하고 PostgreSQL 트랜잭션은 계속 진행.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Coroutine

from app.repositories.kg import KGSyncRepository, create_kg_sync_repository

logger = logging.getLogger(__name__)


class Neo4jSyncHelper:
    """Neo4j 동기화 헬퍼 - 실패 시 로깅만"""

    def __init__(self):
        self._repo: KGSyncRepository | None = None
        self._initialized = False

    @property
    def repo(self) -> KGSyncRepository | None:
        """Lazy 초기화된 KGSyncRepository 반환"""
        if not self._initialized:
            self._repo = create_kg_sync_repository()
            self._initialized = True
        return self._repo

    async def _safe_sync(
        self,
        operation_name: str,
        sync_fn: Callable[[], Coroutine[Any, Any, None]],
    ) -> bool:
        """동기화 실행 (실패 시 로깅만)

        Args:
            operation_name: 작업 이름 (로깅용)
            sync_fn: 실행할 동기화 함수

        Returns:
            bool: 성공 여부
        """
        if not self.repo:
            logger.debug(f"[Neo4j Sync] {operation_name} 건너뜀 (Mock 모드)")
            return False

        try:
            await sync_fn()
            logger.debug(f"[Neo4j Sync] {operation_name} 완료")
            return True
        except Exception as e:
            logger.error(f"[Neo4j Sync] {operation_name} 실패: {e}")
            return False

    # =========================================================================
    # User 동기화
    # =========================================================================

    async def sync_user_create(self, user_id: str, name: str, email: str) -> bool:
        """User 생성 동기화"""
        return await self._safe_sync(
            f"User 생성 ({user_id})",
            lambda: self.repo.upsert_user(user_id, name, email),  # type: ignore
        )

    async def sync_user_update(self, user_id: str, name: str, email: str) -> bool:
        """User 업데이트 동기화"""
        return await self._safe_sync(
            f"User 업데이트 ({user_id})",
            lambda: self.repo.upsert_user(user_id, name, email),  # type: ignore
        )

    async def sync_user_delete(self, user_id: str) -> bool:
        """User 삭제 동기화"""
        return await self._safe_sync(
            f"User 삭제 ({user_id})",
            lambda: self.repo.delete_user(user_id),  # type: ignore
        )

    # =========================================================================
    # Team 동기화
    # =========================================================================

    async def sync_team_create(
        self, team_id: str, name: str, description: str | None
    ) -> bool:
        """Team 생성 동기화"""
        return await self._safe_sync(
            f"Team 생성 ({team_id})",
            lambda: self.repo.upsert_team(team_id, name, description),  # type: ignore
        )

    async def sync_team_update(
        self, team_id: str, name: str, description: str | None
    ) -> bool:
        """Team 업데이트 동기화"""
        return await self._safe_sync(
            f"Team 업데이트 ({team_id})",
            lambda: self.repo.upsert_team(team_id, name, description),  # type: ignore
        )

    async def sync_team_delete(self, team_id: str) -> bool:
        """Team 삭제 동기화"""
        return await self._safe_sync(
            f"Team 삭제 ({team_id})",
            lambda: self.repo.delete_team(team_id),  # type: ignore
        )

    # =========================================================================
    # Meeting 동기화
    # =========================================================================

    async def sync_meeting_create(
        self,
        meeting_id: str,
        team_id: str,
        title: str,
        status: str,
        created_at: datetime,
    ) -> bool:
        """Meeting 생성 동기화"""
        return await self._safe_sync(
            f"Meeting 생성 ({meeting_id})",
            lambda: self.repo.upsert_meeting(  # type: ignore
                meeting_id, team_id, title, status, created_at
            ),
        )

    async def sync_meeting_update(
        self,
        meeting_id: str,
        team_id: str,
        title: str,
        status: str,
        created_at: datetime,
    ) -> bool:
        """Meeting 업데이트 동기화"""
        return await self._safe_sync(
            f"Meeting 업데이트 ({meeting_id})",
            lambda: self.repo.upsert_meeting(  # type: ignore
                meeting_id, team_id, title, status, created_at
            ),
        )

    async def sync_meeting_delete(self, meeting_id: str) -> bool:
        """Meeting 삭제 동기화"""
        return await self._safe_sync(
            f"Meeting 삭제 ({meeting_id})",
            lambda: self.repo.delete_meeting(meeting_id),  # type: ignore
        )

    # =========================================================================
    # TeamMember (MEMBER_OF) 동기화
    # =========================================================================

    async def sync_member_of_create(
        self, user_id: str, team_id: str, role: str
    ) -> bool:
        """MEMBER_OF 관계 생성 동기화"""
        return await self._safe_sync(
            f"MEMBER_OF 생성 ({user_id}->{team_id})",
            lambda: self.repo.upsert_member_of(user_id, team_id, role),  # type: ignore
        )

    async def sync_member_of_update(
        self, user_id: str, team_id: str, role: str
    ) -> bool:
        """MEMBER_OF 관계 업데이트 동기화"""
        return await self._safe_sync(
            f"MEMBER_OF 업데이트 ({user_id}->{team_id})",
            lambda: self.repo.upsert_member_of(user_id, team_id, role),  # type: ignore
        )

    async def sync_member_of_delete(self, user_id: str, team_id: str) -> bool:
        """MEMBER_OF 관계 삭제 동기화"""
        return await self._safe_sync(
            f"MEMBER_OF 삭제 ({user_id}->{team_id})",
            lambda: self.repo.delete_member_of(user_id, team_id),  # type: ignore
        )

    # =========================================================================
    # MeetingParticipant (PARTICIPATED_IN) 동기화
    # =========================================================================

    async def sync_participated_in_create(
        self, user_id: str, meeting_id: str, role: str
    ) -> bool:
        """PARTICIPATED_IN 관계 생성 동기화"""
        return await self._safe_sync(
            f"PARTICIPATED_IN 생성 ({user_id}->{meeting_id})",
            lambda: self.repo.upsert_participated_in(  # type: ignore
                user_id, meeting_id, role
            ),
        )

    async def sync_participated_in_update(
        self, user_id: str, meeting_id: str, role: str
    ) -> bool:
        """PARTICIPATED_IN 관계 업데이트 동기화"""
        return await self._safe_sync(
            f"PARTICIPATED_IN 업데이트 ({user_id}->{meeting_id})",
            lambda: self.repo.upsert_participated_in(  # type: ignore
                user_id, meeting_id, role
            ),
        )

    async def sync_participated_in_delete(
        self, user_id: str, meeting_id: str
    ) -> bool:
        """PARTICIPATED_IN 관계 삭제 동기화"""
        return await self._safe_sync(
            f"PARTICIPATED_IN 삭제 ({user_id}->{meeting_id})",
            lambda: self.repo.delete_participated_in(user_id, meeting_id),  # type: ignore
        )


# 싱글턴 인스턴스
neo4j_sync = Neo4jSyncHelper()
