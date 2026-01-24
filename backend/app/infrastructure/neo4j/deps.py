"""Neo4j 의존성 팩토리

workflow 노드에서 그래프 저장소에 접근할 때 사용.
USE_MOCK_GRAPH 설정에 따라 Mock/실제 구현체 전환.
"""

from app.infrastructure.neo4j.config import USE_MOCK_GRAPH
from app.infrastructure.neo4j.interfaces import (
    IDecisionRepository,
    IMeetingRepository,
    IUserRepository,
)


class Neo4jDeps:
    """Neo4j 의존성 팩토리

    사용 예시:
        from app.infrastructure.neo4j.deps import Neo4jDeps

        # 도메인별 Repository 사용
        async def execute_mit_search(state):
            repo = Neo4jDeps.decision_repo()
            decisions = await repo.get_team_decisions(state["team_id"])
            return {"retrieved_docs": decisions}

        # Decision 생성
        async def save_decision(state):
            repo = Neo4jDeps.decision_repo()
            decision = await repo.create_decision(
                agenda_id=state["agenda_id"],
                decision_id=state["decision_id"],
                content=state["content"],
            )
            return {"created_decision": decision}
    """

    # --- 도메인별 Repository ---

    @staticmethod
    def meeting_repo() -> IMeetingRepository:
        """회의/안건 관련 Repository 반환"""
        if USE_MOCK_GRAPH:
            from app.infrastructure.neo4j.mock.meeting_repository import (
                MockMeetingRepository,
            )
            return MockMeetingRepository()

        raise NotImplementedError(
            "Neo4j not configured yet. Set USE_MOCK_GRAPH=true."
        )

    @staticmethod
    def decision_repo() -> IDecisionRepository:
        """결정사항/액션아이템 관련 Repository 반환 (GT 시스템)"""
        if USE_MOCK_GRAPH:
            from app.infrastructure.neo4j.mock.decision_repository import (
                MockDecisionRepository,
            )
            return MockDecisionRepository()

        raise NotImplementedError(
            "Neo4j not configured yet. Set USE_MOCK_GRAPH=true."
        )

    @staticmethod
    def user_repo() -> IUserRepository:
        """사용자 활동 관련 Repository 반환"""
        if USE_MOCK_GRAPH:
            from app.infrastructure.neo4j.mock.user_repository import (
                MockUserRepository,
            )
            return MockUserRepository()

        raise NotImplementedError(
            "Neo4j not configured yet. Set USE_MOCK_GRAPH=true."
        )

    # --- 헬퍼 메소드 ---

    @staticmethod
    async def get_team_context(team_id: str) -> list[dict]:
        """팀의 GT/결정사항 컨텍스트 조회"""
        repo = Neo4jDeps.decision_repo()
        return await repo.get_team_decisions(team_id)

    @staticmethod
    async def get_meeting_context(meeting_id: str) -> dict | None:
        """회의 컨텍스트 조회"""
        repo = Neo4jDeps.meeting_repo()
        return await repo.get_meeting_with_context(meeting_id)

    @staticmethod
    async def search_gt(
        query: str, team_id: str | None = None, limit: int = 10
    ) -> list[dict]:
        """GT(결정사항) 검색"""
        repo = Neo4jDeps.decision_repo()
        return await repo.search_decisions(query, team_id, limit)
