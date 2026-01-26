"""Neo4j KG Sync Repository

PostgreSQL -> Neo4j 동기화용 Repository.
Raw Cypher 기반, 기존 KGRepository 패턴 준수.
"""

from datetime import datetime
from typing import Any

from neo4j import AsyncDriver


class KGSyncRepository:
    """PostgreSQL -> Neo4j 동기화 Repository - Raw Cypher"""

    def __init__(self, driver: AsyncDriver):
        self.driver = driver

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        """쓰기 쿼리 실행"""

        async def _write_tx(tx):
            result = await tx.run(query, parameters or {})
            return [dict(record) async for record in result]

        async with self.driver.session() as session:
            return await session.execute_write(_write_tx)

    # =========================================================================
    # User 동기화
    # =========================================================================

    async def upsert_user(self, user_id: str, name: str, email: str) -> None:
        """User 노드 upsert (MERGE)"""
        query = """
        MERGE (u:User {id: $user_id})
        SET u.name = $name, u.email = $email, u.updated_at = datetime()
        """
        await self._execute_write(
            query, {"user_id": user_id, "name": name, "email": email}
        )

    async def delete_user(self, user_id: str) -> None:
        """User 노드 삭제 (관계 포함)"""
        query = """
        MATCH (u:User {id: $user_id})
        DETACH DELETE u
        """
        await self._execute_write(query, {"user_id": user_id})

    # =========================================================================
    # Team 동기화
    # =========================================================================

    async def upsert_team(
        self, team_id: str, name: str, description: str | None
    ) -> None:
        """Team 노드 upsert (MERGE)"""
        query = """
        MERGE (t:Team {id: $team_id})
        SET t.name = $name, t.description = $description, t.updated_at = datetime()
        """
        await self._execute_write(
            query, {"team_id": team_id, "name": name, "description": description}
        )

    async def delete_team(self, team_id: str) -> None:
        """Team 노드 삭제 (관계 포함)"""
        query = """
        MATCH (t:Team {id: $team_id})
        DETACH DELETE t
        """
        await self._execute_write(query, {"team_id": team_id})

    # =========================================================================
    # Meeting 동기화
    # =========================================================================

    async def upsert_meeting(
        self,
        meeting_id: str,
        team_id: str,
        title: str,
        status: str,
        created_at: datetime,
    ) -> None:
        """Meeting 노드 upsert + HOSTS 관계 생성"""
        query = """
        MERGE (m:Meeting {id: $meeting_id})
        SET m.title = $title, m.status = $status,
            m.created_at = datetime($created_at), m.updated_at = datetime()
        WITH m
        MATCH (t:Team {id: $team_id})
        MERGE (t)-[:HOSTS]->(m)
        """
        await self._execute_write(
            query,
            {
                "meeting_id": meeting_id,
                "team_id": team_id,
                "title": title,
                "status": status,
                "created_at": created_at.isoformat() if created_at else None,
            },
        )

    async def delete_meeting(self, meeting_id: str) -> None:
        """Meeting 노드 삭제 (관계 포함)"""
        query = """
        MATCH (m:Meeting {id: $meeting_id})
        DETACH DELETE m
        """
        await self._execute_write(query, {"meeting_id": meeting_id})

    # =========================================================================
    # TeamMember (MEMBER_OF 관계) 동기화
    # =========================================================================

    async def upsert_member_of(
        self, user_id: str, team_id: str, role: str
    ) -> None:
        """MEMBER_OF 관계 upsert"""
        query = """
        MATCH (u:User {id: $user_id}), (t:Team {id: $team_id})
        MERGE (u)-[r:MEMBER_OF]->(t)
        SET r.role = $role, r.updated_at = datetime()
        """
        await self._execute_write(
            query, {"user_id": user_id, "team_id": team_id, "role": role}
        )

    async def delete_member_of(self, user_id: str, team_id: str) -> None:
        """MEMBER_OF 관계 삭제"""
        query = """
        MATCH (u:User {id: $user_id})-[r:MEMBER_OF]->(t:Team {id: $team_id})
        DELETE r
        """
        await self._execute_write(query, {"user_id": user_id, "team_id": team_id})

    # =========================================================================
    # MeetingParticipant (PARTICIPATED_IN 관계) 동기화
    # =========================================================================

    async def upsert_participated_in(
        self, user_id: str, meeting_id: str, role: str
    ) -> None:
        """PARTICIPATED_IN 관계 upsert"""
        query = """
        MATCH (u:User {id: $user_id}), (m:Meeting {id: $meeting_id})
        MERGE (u)-[r:PARTICIPATED_IN]->(m)
        SET r.role = $role, r.updated_at = datetime()
        """
        await self._execute_write(
            query, {"user_id": user_id, "meeting_id": meeting_id, "role": role}
        )

    async def delete_participated_in(self, user_id: str, meeting_id: str) -> None:
        """PARTICIPATED_IN 관계 삭제"""
        query = """
        MATCH (u:User {id: $user_id})-[r:PARTICIPATED_IN]->(m:Meeting {id: $meeting_id})
        DELETE r
        """
        await self._execute_write(
            query, {"user_id": user_id, "meeting_id": meeting_id}
        )

    # =========================================================================
    # 배치 동기화 (마이그레이션용 - UNWIND 기반)
    # =========================================================================

    async def batch_upsert_users(self, users: list[dict]) -> int:
        """User 노드 배치 upsert

        Args:
            users: [{"id": str, "name": str, "email": str}, ...]

        Returns:
            처리된 건수
        """
        if not users:
            return 0
        query = """
        UNWIND $users AS u
        MERGE (user:User {id: u.id})
        SET user.name = u.name, user.email = u.email, user.updated_at = datetime()
        RETURN count(*) AS cnt
        """
        result = await self._execute_write(query, {"users": users})
        return result[0]["cnt"] if result else 0

    async def batch_upsert_teams(self, teams: list[dict]) -> int:
        """Team 노드 배치 upsert

        Args:
            teams: [{"id": str, "name": str, "description": str | None}, ...]

        Returns:
            처리된 건수
        """
        if not teams:
            return 0
        query = """
        UNWIND $teams AS t
        MERGE (team:Team {id: t.id})
        SET team.name = t.name, team.description = t.description, team.updated_at = datetime()
        RETURN count(*) AS cnt
        """
        result = await self._execute_write(query, {"teams": teams})
        return result[0]["cnt"] if result else 0

    async def batch_upsert_meetings(self, meetings: list[dict]) -> int:
        """Meeting 노드 배치 upsert + HOSTS 관계 생성

        Args:
            meetings: [{"id": str, "team_id": str, "title": str, "status": str, "created_at": str}, ...]

        Returns:
            처리된 건수
        """
        if not meetings:
            return 0
        query = """
        UNWIND $meetings AS m
        MERGE (meeting:Meeting {id: m.id})
        SET meeting.title = m.title, meeting.status = m.status,
            meeting.created_at = datetime(m.created_at), meeting.updated_at = datetime()
        WITH meeting, m
        MATCH (t:Team {id: m.team_id})
        MERGE (t)-[:HOSTS]->(meeting)
        RETURN count(*) AS cnt
        """
        result = await self._execute_write(query, {"meetings": meetings})
        return result[0]["cnt"] if result else 0

    async def batch_upsert_member_of(self, members: list[dict]) -> int:
        """MEMBER_OF 관계 배치 upsert

        Args:
            members: [{"user_id": str, "team_id": str, "role": str}, ...]

        Returns:
            처리된 건수
        """
        if not members:
            return 0
        query = """
        UNWIND $members AS m
        MATCH (u:User {id: m.user_id}), (t:Team {id: m.team_id})
        MERGE (u)-[r:MEMBER_OF]->(t)
        SET r.role = m.role, r.updated_at = datetime()
        RETURN count(*) AS cnt
        """
        result = await self._execute_write(query, {"members": members})
        return result[0]["cnt"] if result else 0

    async def batch_upsert_participated_in(self, participants: list[dict]) -> int:
        """PARTICIPATED_IN 관계 배치 upsert

        Args:
            participants: [{"user_id": str, "meeting_id": str, "role": str}, ...]

        Returns:
            처리된 건수
        """
        if not participants:
            return 0
        query = """
        UNWIND $participants AS p
        MATCH (u:User {id: p.user_id}), (m:Meeting {id: p.meeting_id})
        MERGE (u)-[r:PARTICIPATED_IN]->(m)
        SET r.role = p.role, r.updated_at = datetime()
        RETURN count(*) AS cnt
        """
        result = await self._execute_write(query, {"participants": participants})
        return result[0]["cnt"] if result else 0

    # =========================================================================
    # 전체 동기화 (마이그레이션용)
    # =========================================================================

    async def clear_sync_data(self) -> None:
        """동기화 대상 데이터만 초기화 (GT 데이터 유지)

        삭제 대상: User, Team, Meeting 노드 및 관련 관계 (MEMBER_OF, HOSTS, PARTICIPATED_IN)
        유지 대상: Agenda, Decision, ActionItem 노드 (GT 시스템)
        """
        # 관계 삭제
        await self._execute_write(
            "MATCH ()-[r:MEMBER_OF]->() DELETE r", {}
        )
        await self._execute_write(
            "MATCH ()-[r:HOSTS]->() DELETE r", {}
        )
        await self._execute_write(
            "MATCH ()-[r:PARTICIPATED_IN]->() DELETE r", {}
        )

        # GT 관계가 없는 노드만 삭제
        await self._execute_write(
            """
            MATCH (u:User)
            WHERE NOT (u)-[:APPROVED_BY]->() AND NOT (u)-[:REJECTED_BY]->()
                  AND NOT (u)-[:ASSIGNED_TO]->()
            DELETE u
            """,
            {},
        )
        await self._execute_write("MATCH (t:Team) DELETE t", {})
        await self._execute_write(
            """
            MATCH (m:Meeting)
            WHERE NOT (m)-[:CONTAINS]->()
            DELETE m
            """,
            {},
        )
