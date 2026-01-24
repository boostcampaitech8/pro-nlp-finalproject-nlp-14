"""Neo4j 저장소 인터페이스 정의

실제 Neo4j 구현과 Mock 구현이 동일한 인터페이스를 따르도록 정의.
"""

from abc import ABC, abstractmethod
from typing import Any


class IGraphRepository(ABC):
    """기본 그래프 저장소 인터페이스"""

    @abstractmethod
    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        """읽기 쿼리 실행"""
        pass

    @abstractmethod
    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        """쓰기 쿼리 실행"""
        pass


class IMeetingRepository(ABC):
    """회의/안건 관련 저장소 인터페이스"""

    @abstractmethod
    async def get_meeting_with_context(self, meeting_id: str) -> dict | None:
        """회의와 관련 컨텍스트(팀, 안건, 결정사항, 참여자) 조회"""
        pass

    @abstractmethod
    async def get_meeting_minutes(self, meeting_id: str) -> dict | None:
        """회의록(Minutes) 조회"""
        pass

    @abstractmethod
    async def list_meeting_minutes(self, team_id: str | None = None) -> list[dict]:
        """회의록 목록 조회"""
        pass

    @abstractmethod
    async def create_agenda(
        self,
        meeting_id: str,
        agenda_id: str,
        topic: str,
        description: str | None = None,
    ) -> dict:
        """안건 노드 생성 + CONTAINS 관계"""
        pass


class IDecisionRepository(ABC):
    """결정사항/액션아이템 관련 저장소 인터페이스 (GT 시스템)"""

    @abstractmethod
    async def get_team_decisions(
        self, team_id: str, status: str = "latest"
    ) -> list[dict]:
        """팀의 결정사항(GT) 조회"""
        pass

    @abstractmethod
    async def search_decisions(
        self, query: str, team_id: str | None = None, limit: int = 10
    ) -> list[dict]:
        """결정사항 검색"""
        pass

    @abstractmethod
    async def create_decision(
        self,
        agenda_id: str,
        decision_id: str,
        content: str,
        context: str | None = None,
    ) -> dict:
        """Decision 노드 생성 + HAS_DECISION 관계"""
        pass

    @abstractmethod
    async def create_action_item(
        self,
        decision_id: str,
        action_item_id: str,
        title: str,
        assignee_id: str,
        description: str | None = None,
        due_date: str | None = None,
    ) -> dict:
        """ActionItem 노드 생성 + TRIGGERS, ASSIGNED_TO 관계"""
        pass

    @abstractmethod
    async def link_user_decision(
        self, user_id: str, decision_id: str, status: str = "approved"
    ) -> None:
        """REVIEWED_BY 관계 생성"""
        pass


class IUserRepository(ABC):
    """사용자 활동 관련 저장소 인터페이스"""

    @abstractmethod
    async def get_user_activity(self, user_id: str) -> dict:
        """사용자 활동 요약 (팀/회의/액션아이템 수)"""
        pass

    @abstractmethod
    async def get_pending_action_items(self, user_id: str) -> list[dict]:
        """사용자의 미완료 액션아이템 조회"""
        pass
