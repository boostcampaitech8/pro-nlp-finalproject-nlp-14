# Neo4j Mocking Strategy

Neo4j 실제 구현 전 개발 단계에서 사용할 Mocking 전략

## 1. 인터페이스 추상화

`backend/app/repositories/interfaces.py`:

```python
from abc import ABC, abstractmethod
from typing import Any, Protocol


class GraphSessionProtocol(Protocol):
    """Neo4j 세션 프로토콜"""

    async def run(self, query: str, parameters: dict[str, Any] | None = None) -> Any:
        ...

    async def close(self) -> None:
        ...


class IGraphRepository(ABC):
    """그래프 저장소 인터페이스"""

    @abstractmethod
    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        pass

    @abstractmethod
    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        pass


class IMeetingGraphRepository(ABC):
    """회의 그래프 저장소 인터페이스"""

    @abstractmethod
    async def get_meeting_with_context(self, meeting_id: str) -> dict | None:
        pass

    @abstractmethod
    async def get_team_decisions(
        self, team_id: str, status: str = "latest"
    ) -> list[dict]:
        pass

    @abstractmethod
    async def create_decision(
        self,
        agenda_id: str,
        decision_id: str,
        content: str,
        context: str | None = None,
    ) -> dict:
        pass


class IUserGraphRepository(ABC):
    """사용자 그래프 저장소 인터페이스"""

    @abstractmethod
    async def get_user_activity(self, user_id: str) -> dict:
        pass

    @abstractmethod
    async def get_pending_action_items(self, user_id: str) -> list[dict]:
        pass
```

## 2. Mock 구현체

`backend/app/repositories/mock_graph_repository.py`:

```python
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.repositories.interfaces import (
    IGraphRepository,
    IMeetingGraphRepository,
    IUserGraphRepository,
)


# Mock 데이터 저장소 (인메모리)
MOCK_DATA = {
    "teams": {
        "team-1": {"id": "team-1", "name": "개발팀", "description": "백엔드/프론트엔드 개발"},
        "team-2": {"id": "team-2", "name": "기획팀", "description": "제품 기획"},
    },
    "users": {
        "user-1": {"id": "user-1", "name": "김민준", "email": "minjun@example.com"},
        "user-2": {"id": "user-2", "name": "이서연", "email": "seoyeon@example.com"},
    },
    "meetings": {
        "meeting-1": {
            "id": "meeting-1",
            "title": "스프린트 계획 회의",
            "status": "completed",
            "team_id": "team-1",
            "participant_ids": ["user-1", "user-2"],
        },
    },
    "agendas": {
        "agenda-1": {
            "id": "agenda-1",
            "topic": "API 설계 검토",
            "meeting_id": "meeting-1",
        },
    },
    "decisions": {
        "decision-1": {
            "id": "decision-1",
            "content": "RESTful API 설계 원칙 준수",
            "context": "API 일관성 유지를 위해",
            "status": "latest",
            "agenda_id": "agenda-1",
            "created_at": datetime.now().isoformat(),
        },
    },
    "action_items": {
        "action-1": {
            "id": "action-1",
            "title": "API 문서 작성",
            "status": "pending",
            "due_date": "2024-02-01",
            "assignee_id": "user-1",
            "decision_id": "decision-1",
        },
    },
}


class MockGraphRepository(IGraphRepository):
    """Mock 그래프 저장소"""

    def __init__(self, data: dict | None = None):
        self.data = data or MOCK_DATA

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        # Mock에서는 쿼리 파싱 대신 직접 데이터 반환
        return []

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        return []


class MockMeetingGraphRepository(IMeetingGraphRepository):
    """Mock 회의 그래프 저장소"""

    def __init__(self, data: dict | None = None):
        self.data = data or MOCK_DATA

    async def get_meeting_with_context(self, meeting_id: str) -> dict | None:
        meeting = self.data["meetings"].get(meeting_id)
        if not meeting:
            return None

        team = self.data["teams"].get(meeting.get("team_id"))
        participants = [
            self.data["users"].get(uid)
            for uid in meeting.get("participant_ids", [])
            if self.data["users"].get(uid)
        ]
        agendas = [
            a for a in self.data["agendas"].values()
            if a.get("meeting_id") == meeting_id
        ]
        decisions = [
            d for d in self.data["decisions"].values()
            if d.get("agenda_id") in [a["id"] for a in agendas]
            and d.get("status") == "latest"
        ]

        return {
            "meeting": meeting,
            "team": team,
            "agendas": agendas,
            "decisions": decisions,
            "participants": participants,
        }

    async def get_team_decisions(
        self, team_id: str, status: str = "latest"
    ) -> list[dict]:
        # 팀의 회의 찾기
        team_meetings = [
            m for m in self.data["meetings"].values()
            if m.get("team_id") == team_id
        ]
        meeting_ids = [m["id"] for m in team_meetings]

        # 회의의 안건 찾기
        agendas = [
            a for a in self.data["agendas"].values()
            if a.get("meeting_id") in meeting_ids
        ]
        agenda_ids = [a["id"] for a in agendas]

        # 안건의 결정사항 찾기
        decisions = [
            {
                "id": d["id"],
                "content": d["content"],
                "context": d.get("context"),
                "meeting_title": next(
                    (m["title"] for m in team_meetings
                     if m["id"] == next(
                         (a["meeting_id"] for a in agendas if a["id"] == d["agenda_id"]),
                         None
                     )),
                    None
                ),
                "agenda_topic": next(
                    (a["topic"] for a in agendas if a["id"] == d["agenda_id"]),
                    None
                ),
                "created_at": d.get("created_at"),
            }
            for d in self.data["decisions"].values()
            if d.get("agenda_id") in agenda_ids and d.get("status") == status
        ]

        return decisions

    async def create_decision(
        self,
        agenda_id: str,
        decision_id: str,
        content: str,
        context: str | None = None,
    ) -> dict:
        decision = {
            "id": decision_id,
            "content": content,
            "context": context,
            "status": "latest",
            "agenda_id": agenda_id,
            "created_at": datetime.now().isoformat(),
        }
        self.data["decisions"][decision_id] = decision
        return decision


class MockUserGraphRepository(IUserGraphRepository):
    """Mock 사용자 그래프 저장소"""

    def __init__(self, data: dict | None = None):
        self.data = data or MOCK_DATA

    async def get_user_activity(self, user_id: str) -> dict:
        user = self.data["users"].get(user_id)
        if not user:
            return {}

        # 팀 수
        team_count = sum(
            1 for t in self.data["teams"].values()
            # 실제로는 MEMBER_OF 관계 확인 필요
        )

        # 회의 수
        meeting_count = sum(
            1 for m in self.data["meetings"].values()
            if user_id in m.get("participant_ids", [])
        )

        # 액션아이템 수
        action_item_count = sum(
            1 for ai in self.data["action_items"].values()
            if ai.get("assignee_id") == user_id
        )

        return {
            "name": user["name"],
            "team_count": team_count,
            "meeting_count": meeting_count,
            "decision_count": 0,  # 간략화
            "action_item_count": action_item_count,
        }

    async def get_pending_action_items(self, user_id: str) -> list[dict]:
        return [
            {
                "id": ai["id"],
                "title": ai["title"],
                "status": ai["status"],
                "due_date": ai.get("due_date"),
                "from_decision": self.data["decisions"]
                    .get(ai.get("decision_id"), {})
                    .get("content"),
            }
            for ai in self.data["action_items"].values()
            if ai.get("assignee_id") == user_id
            and ai.get("status") in ["pending", "in_progress"]
        ]
```

## 3. 의존성 주입 전환

`backend/app/api/dependencies.py`:

```python
from typing import Annotated
from fastapi import Depends

from app.core.config import get_settings
from app.repositories.interfaces import IMeetingGraphRepository, IUserGraphRepository


def get_meeting_graph_repository() -> IMeetingGraphRepository:
    """환경에 따라 실제/Mock 저장소 반환"""
    settings = get_settings()

    if settings.app_env == "test" or settings.use_mock_graph:
        from app.repositories.mock_graph_repository import MockMeetingGraphRepository
        return MockMeetingGraphRepository()
    else:
        # 실제 구현 (Neo4j 연결 후)
        from app.repositories.graph_repository import MeetingGraphRepository
        from app.core.neo4j import get_neo4j_session
        # 세션 주입 필요 - 실제 구현 시 수정
        raise NotImplementedError("Neo4j not configured yet")


def get_user_graph_repository() -> IUserGraphRepository:
    """환경에 따라 실제/Mock 저장소 반환"""
    settings = get_settings()

    if settings.app_env == "test" or settings.use_mock_graph:
        from app.repositories.mock_graph_repository import MockUserGraphRepository
        return MockUserGraphRepository()
    else:
        raise NotImplementedError("Neo4j not configured yet")


MeetingGraphRepo = Annotated[IMeetingGraphRepository, Depends(get_meeting_graph_repository)]
UserGraphRepo = Annotated[IUserGraphRepository, Depends(get_user_graph_repository)]
```

## 4. 설정에 플래그 추가

`backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # ... 기존 설정 ...

    # Mock 설정
    use_mock_graph: bool = True  # Neo4j 구현 전 True
```

## 5. 테스트 Fixture

`backend/tests/conftest.py`:

```python
import pytest
from app.repositories.mock_graph_repository import (
    MockMeetingGraphRepository,
    MockUserGraphRepository,
    MOCK_DATA,
)


@pytest.fixture
def mock_data():
    """테스트용 Mock 데이터 (복사본)"""
    import copy
    return copy.deepcopy(MOCK_DATA)


@pytest.fixture
def meeting_graph_repo(mock_data):
    """테스트용 회의 그래프 저장소"""
    return MockMeetingGraphRepository(mock_data)


@pytest.fixture
def user_graph_repo(mock_data):
    """테스트용 사용자 그래프 저장소"""
    return MockUserGraphRepository(mock_data)
```

## 6. 테스트 예시

`backend/tests/test_graph_repository.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_get_meeting_with_context(meeting_graph_repo):
    result = await meeting_graph_repo.get_meeting_with_context("meeting-1")

    assert result is not None
    assert result["meeting"]["title"] == "스프린트 계획 회의"
    assert result["team"]["name"] == "개발팀"
    assert len(result["participants"]) == 2


@pytest.mark.asyncio
async def test_get_team_decisions(meeting_graph_repo):
    result = await meeting_graph_repo.get_team_decisions("team-1")

    assert len(result) >= 1
    assert result[0]["content"] == "RESTful API 설계 원칙 준수"


@pytest.mark.asyncio
async def test_create_decision(meeting_graph_repo):
    result = await meeting_graph_repo.create_decision(
        agenda_id="agenda-1",
        decision_id="decision-new",
        content="새로운 결정사항",
        context="테스트 컨텍스트",
    )

    assert result["id"] == "decision-new"
    assert result["status"] == "latest"


@pytest.mark.asyncio
async def test_get_pending_action_items(user_graph_repo):
    result = await user_graph_repo.get_pending_action_items("user-1")

    assert len(result) >= 1
    assert result[0]["title"] == "API 문서 작성"
```

## 7. 실제 구현 전환 체크리스트

Neo4j 실제 구현 시:

1. [ ] `use_mock_graph` 플래그를 `False`로 변경
2. [ ] `get_meeting_graph_repository()`에서 실제 구현체 반환
3. [ ] `get_user_graph_repository()`에서 실제 구현체 반환
4. [ ] 통합 테스트 추가
5. [ ] Mock 코드는 테스트용으로 유지
