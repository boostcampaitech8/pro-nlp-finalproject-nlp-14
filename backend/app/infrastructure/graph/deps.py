"""그래프 의존성 팩토리

workflow 노드에서 그래프 저장소에 접근할 때 사용.
USE_MOCK_GRAPH 설정에 따라 Mock/실제 구현체 전환.
"""

from app.infrastructure.graph.config import USE_MOCK_GRAPH
from app.infrastructure.graph.integration.llm import llm


class GraphDeps:
    """그래프 노드에서 사용할 의존성 팩토리

    사용 예시:
        from app.infrastructure.graph.deps import GraphDeps

        async def execute_mit_search(state):
            repo = GraphDeps.get_graph_repo()
            decisions = await repo.get_team_decisions(state["team_id"])
            return {"retrieved_docs": decisions}
    """

    @staticmethod
    def get_llm():
        """LLM 인스턴스 반환"""
        return llm

    @staticmethod
    def get_graph_repo():
        """그래프 저장소 인스턴스 반환

        USE_MOCK_GRAPH=True면 Mock, False면 실제 Neo4j 연결.
        """
        if USE_MOCK_GRAPH:
            from app.infrastructure.graph.mock.graph_repository import (
                MockGraphRepository,
            )
            return MockGraphRepository()

        # 실제 Neo4j 연결 (Phase 3에서 구현)
        # from app.infrastructure.graph.integration.neo4j import Neo4jGraphRepository
        # return Neo4jGraphRepository()
        raise NotImplementedError(
            "Neo4j not configured yet. Set USE_MOCK_GRAPH=true or implement Neo4jGraphRepository."
        )

    @staticmethod
    async def get_team_context(team_id: str) -> list[dict]:
        """팀의 GT/결정사항 컨텍스트 조회

        Args:
            team_id: 팀 ID

        Returns:
            결정사항 목록
        """
        repo = GraphDeps.get_graph_repo()
        return await repo.get_team_decisions(team_id)

    @staticmethod
    async def get_meeting_context(meeting_id: str) -> dict | None:
        """회의 컨텍스트 조회

        Args:
            meeting_id: 회의 ID

        Returns:
            회의 관련 전체 컨텍스트
        """
        repo = GraphDeps.get_graph_repo()
        return await repo.get_meeting_with_context(meeting_id)

    @staticmethod
    async def search_gt(
        query: str, team_id: str | None = None, limit: int = 10
    ) -> list[dict]:
        """GT(결정사항) 검색

        Args:
            query: 검색어
            team_id: 팀 ID (선택적)
            limit: 최대 결과 수

        Returns:
            매칭된 결정사항 목록
        """
        repo = GraphDeps.get_graph_repo()
        return await repo.search_decisions(query, team_id, limit)
