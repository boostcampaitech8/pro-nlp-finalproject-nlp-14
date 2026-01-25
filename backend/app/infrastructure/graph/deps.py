"""LangGraph 오케스트레이션 의존성 팩토리

workflow 노드에서 사용하는 의존성 (LLM, Neo4j Repository).
Neo4j Repository는 infrastructure/neo4j 모듈에서 가져옴.
"""

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.neo4j.deps import Neo4jDeps
from app.infrastructure.neo4j.interfaces import (
    IDecisionRepository,
    IMeetingRepository,
    IUserRepository,
)


class GraphDeps:
    """LangGraph 노드에서 사용할 의존성 팩토리

    사용 예시:
        from app.infrastructure.graph.deps import GraphDeps

        # LLM 사용
        async def generate_response(state):
            llm = GraphDeps.get_llm()
            response = await llm.ainvoke(state["messages"])
            return {"response": response}

        # 도메인별 Repository 사용
        async def execute_mit_search(state):
            repo = GraphDeps.decision_repo()
            decisions = await repo.get_team_decisions(state["team_id"])
            return {"retrieved_docs": decisions}
    """

    @staticmethod
    def get_llm():
        """LLM 인스턴스 반환"""
        return llm

    # --- Neo4j Repository (neo4j 모듈에 위임) ---

    @staticmethod
    def meeting_repo() -> IMeetingRepository:
        """회의/안건 관련 Repository 반환"""
        return Neo4jDeps.meeting_repo()

    @staticmethod
    def decision_repo() -> IDecisionRepository:
        """결정사항/액션아이템 관련 Repository 반환 (GT 시스템)"""
        return Neo4jDeps.decision_repo()

    @staticmethod
    def user_repo() -> IUserRepository:
        """사용자 활동 관련 Repository 반환"""
        return Neo4jDeps.user_repo()

    # --- 헬퍼 메소드 (neo4j 모듈에 위임) ---

    @staticmethod
    async def get_team_context(team_id: str) -> list[dict]:
        """팀의 GT/결정사항 컨텍스트 조회"""
        return await Neo4jDeps.get_team_context(team_id)

    @staticmethod
    async def get_meeting_context(meeting_id: str) -> dict | None:
        """회의 컨텍스트 조회"""
        return await Neo4jDeps.get_meeting_context(meeting_id)

    @staticmethod
    async def search_gt(
        query: str, team_id: str | None = None, limit: int = 10
    ) -> list[dict]:
        """GT(결정사항) 검색"""
        return await Neo4jDeps.search_gt(query, team_id, limit)
