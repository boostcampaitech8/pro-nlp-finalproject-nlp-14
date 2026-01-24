# Neo4j Usage Patterns

Backend에서 Neo4j를 사용하기 위한 패턴 및 코드 예시

## 1. 패키지 설치

```bash
cd backend
uv add neo4j
```

## 2. 설정 클래스

`backend/app/core/config.py`에 추가:

```python
class Settings(BaseSettings):
    # ... 기존 설정 ...

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4jpassword"

    class Config:
        env_file = ".env"
```

## 3. 드라이버 설정

`backend/app/core/neo4j.py`:

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession


class Neo4jDriver:
    """Neo4j 비동기 드라이버 싱글톤"""

    _driver: AsyncDriver | None = None

    @classmethod
    async def get_driver(cls, uri: str, user: str, password: str) -> AsyncDriver:
        if cls._driver is None:
            cls._driver = AsyncGraphDatabase.driver(
                uri,
                auth=(user, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )
            # 연결 확인
            await cls._driver.verify_connectivity()
        return cls._driver

    @classmethod
    async def close(cls) -> None:
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None


@asynccontextmanager
async def get_neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """Neo4j 세션 컨텍스트 매니저"""
    from app.core.config import get_settings

    settings = get_settings()
    driver = await Neo4jDriver.get_driver(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
    )

    session = driver.session(database="neo4j")
    try:
        yield session
    finally:
        await session.close()
```

## 4. 의존성 주입

`backend/app/api/dependencies.py`에 추가:

```python
from typing import Annotated
from fastapi import Depends
from neo4j import AsyncSession
from app.core.neo4j import get_neo4j_session


async def get_graph_session() -> AsyncSession:
    """FastAPI 의존성으로 Neo4j 세션 제공"""
    async with get_neo4j_session() as session:
        yield session


GraphSession = Annotated[AsyncSession, Depends(get_graph_session)]
```

## 5. Repository 패턴

`backend/app/repositories/graph_repository.py`:

```python
from typing import Any
from neo4j import AsyncSession, Record


class GraphRepository:
    """Neo4j 그래프 저장소 기본 클래스"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None
    ) -> list[Record]:
        """읽기 쿼리 실행"""
        result = await self.session.run(query, parameters or {})
        return [record async for record in result]

    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None
    ) -> list[Record]:
        """쓰기 쿼리 실행 (트랜잭션 내)"""
        async def _write_tx(tx):
            result = await tx.run(query, parameters or {})
            return [record async for record in result]

        return await self.session.execute_write(_write_tx)


class MeetingGraphRepository(GraphRepository):
    """회의 관련 그래프 쿼리"""

    async def get_meeting_with_context(self, meeting_id: str) -> dict | None:
        """회의와 관련 노드 조회"""
        query = """
        MATCH (t:Team)-[:HOSTS]->(m:Meeting {id: $meeting_id})
        OPTIONAL MATCH (m)-[:CONTAINS]->(a:Agenda)
        OPTIONAL MATCH (a)-[:HAS_DECISION]->(d:Decision {status: 'latest'})
        OPTIONAL MATCH (u:User)-[:PARTICIPATED_IN]->(m)
        RETURN m, t, collect(DISTINCT a) AS agendas,
               collect(DISTINCT d) AS decisions,
               collect(DISTINCT u) AS participants
        """
        records = await self.execute_read(query, {"meeting_id": meeting_id})
        if not records:
            return None

        record = records[0]
        return {
            "meeting": dict(record["m"]),
            "team": dict(record["t"]),
            "agendas": [dict(a) for a in record["agendas"]],
            "decisions": [dict(d) for d in record["decisions"]],
            "participants": [dict(u) for u in record["participants"]],
        }

    async def get_team_decisions(
        self,
        team_id: str,
        status: str = "latest"
    ) -> list[dict]:
        """팀의 GT(결정사항) 조회"""
        query = """
        MATCH (t:Team {id: $team_id})-[:HOSTS]->(m:Meeting)
              -[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision {status: $status})
        RETURN d.id AS id, d.content AS content, d.context AS context,
               m.title AS meeting_title, a.topic AS agenda_topic,
               d.created_at AS created_at
        ORDER BY d.created_at DESC
        """
        records = await self.execute_read(query, {
            "team_id": team_id,
            "status": status
        })
        return [dict(r) for r in records]

    async def create_decision(
        self,
        agenda_id: str,
        decision_id: str,
        content: str,
        context: str | None = None,
    ) -> dict:
        """새 결정사항 생성"""
        query = """
        MATCH (a:Agenda {id: $agenda_id})
        CREATE (d:Decision {
            id: $decision_id,
            content: $content,
            context: $context,
            status: 'latest',
            created_at: datetime()
        })
        CREATE (a)-[:HAS_DECISION]->(d)
        RETURN d
        """
        records = await self.execute_write(query, {
            "agenda_id": agenda_id,
            "decision_id": decision_id,
            "content": content,
            "context": context,
        })
        return dict(records[0]["d"]) if records else {}


class UserGraphRepository(GraphRepository):
    """사용자 관련 그래프 쿼리"""

    async def get_user_activity(self, user_id: str) -> dict:
        """사용자 활동 요약"""
        query = """
        MATCH (u:User {id: $user_id})
        OPTIONAL MATCH (u)-[:MEMBER_OF]->(t:Team)
        OPTIONAL MATCH (u)-[:PARTICIPATED_IN]->(m:Meeting)
        OPTIONAL MATCH (u)-[:REVIEWED_BY]->(d:Decision)
        OPTIONAL MATCH (u)-[:ASSIGNED_TO]->(ai:ActionItem)
        RETURN u.name AS name,
               count(DISTINCT t) AS team_count,
               count(DISTINCT m) AS meeting_count,
               count(DISTINCT d) AS decision_count,
               count(DISTINCT ai) AS action_item_count
        """
        records = await self.execute_read(query, {"user_id": user_id})
        return dict(records[0]) if records else {}

    async def get_pending_action_items(self, user_id: str) -> list[dict]:
        """미완료 액션아이템 조회"""
        query = """
        MATCH (u:User {id: $user_id})-[:ASSIGNED_TO]->(ai:ActionItem)
        WHERE ai.status IN ['pending', 'in_progress']
        OPTIONAL MATCH (d:Decision)-[:TRIGGERS]->(ai)
        RETURN ai.id AS id, ai.title AS title, ai.status AS status,
               ai.due_date AS due_date, d.content AS from_decision
        ORDER BY ai.due_date
        """
        records = await self.execute_read(query, {"user_id": user_id})
        return [dict(r) for r in records]
```

## 6. 서비스에서 사용

`backend/app/services/graph_service.py`:

```python
from neo4j import AsyncSession
from app.repositories.graph_repository import MeetingGraphRepository


class GraphService:
    """그래프 데이터 서비스"""

    def __init__(self, session: AsyncSession):
        self.meeting_repo = MeetingGraphRepository(session)

    async def get_meeting_knowledge(self, meeting_id: str) -> dict | None:
        """회의 관련 지식 그래프 조회"""
        return await self.meeting_repo.get_meeting_with_context(meeting_id)

    async def get_team_ground_truth(self, team_id: str) -> list[dict]:
        """팀의 Ground Truth 조회"""
        return await self.meeting_repo.get_team_decisions(team_id)
```

## 7. 엔드포인트 예시

`backend/app/api/v1/endpoints/graph.py`:

```python
from fastapi import APIRouter
from app.api.dependencies import GraphSession
from app.services.graph_service import GraphService

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/meetings/{meeting_id}/knowledge")g
async def get_meeting_knowledge(
    meeting_id: str,
    session: GraphSession,
):
    """회의 관련 지식 그래프 조회"""
    service = GraphService(session)
    result = await service.get_meeting_knowledge(meeting_id)
    if not result:
        raise HTTPException(404, "Meeting not found")
    return result


@router.get("/teams/{team_id}/decisions")
async def get_team_decisions(
    team_id: str,
    session: GraphSession,
):
    """팀의 GT 목록 조회"""
    service = GraphService(session)
    return await service.get_team_ground_truth(team_id)
```

## 8. 애플리케이션 수명주기

`backend/app/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.neo4j import Neo4jDriver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    yield
    # 종료 시
    await Neo4jDriver.close()


app = FastAPI(lifespan=lifespan)
```

## 9. 트랜잭션 패턴

```python
# 읽기 전용 (자동 재시도)
async with get_neo4j_session() as session:
    result = await session.execute_read(
        lambda tx: tx.run("MATCH (n) RETURN n LIMIT 10")
    )

# 쓰기 (자동 재시도 + 롤백)
async with get_neo4j_session() as session:
    result = await session.execute_write(
        lambda tx: tx.run("CREATE (n:Test {name: $name}) RETURN n", name="test")
    )
```
