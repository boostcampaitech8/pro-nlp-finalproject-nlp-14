# Neo4j 동기화 전략

PostgreSQL과 Neo4j 간 데이터 동기화 전략

## 1. 아키텍처 개요

### Polyglot Persistence

```
┌─────────────────────────────────────────────────────────┐
│                 Mit Polyglot Architecture               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   PostgreSQL (SSOT)     Neo4j              Redis        │
│   ┌──────────────┐     ┌──────────────┐   ┌─────────┐  │
│   │ User, Team   │ ──→ │ 동기화된 노드  │   │ 캐시    │  │
│   │ Meeting      │     │ + GT 데이터   │   │ ARQ 큐  │  │
│   │ Participant  │     │ + 관계 탐색   │   │         │  │
│   └──────────────┘     └──────────────┘   └─────────┘  │
│         │                     │                         │
│         └─────────────────────┼─────────────────────────┤
│                               │                         │
│                    ┌──────────────────┐                 │
│                    │   Backend        │                 │
│                    │   서비스 레이어   │                 │
│                    └──────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

### 설계 원칙

1. **PostgreSQL이 원본 (SSOT)** - 모든 기본 엔티티의 진실의 원천
2. **Neo4j는 그래프 관계 + GT 전용 데이터 저장** - Agenda, Decision, ActionItem
3. **서비스 레이어에서 실시간 동기화** - 별도 워커 불필요
4. **동기화 실패 시 로깅 후 수동/자동 복구** - PostgreSQL 롤백하지 않음

### 데이터 분리

| 저장소 | 데이터 | 역할 |
|--------|--------|------|
| PostgreSQL | User, Team, Meeting, Participant, Recording, Transcript | SSOT, CRUD, 트랜잭션 |
| Neo4j | User*, Team*, Meeting* + Agenda, Decision, ActionItem | GT 시스템, 그래프 쿼리 |
| Redis | 세션, 캐시, ARQ 작업 큐 | 성능 최적화 |

*동기화 대상

## 2. 접근 방식 분리 (OGM vs Raw Driver)

| 작업 유형 | 도구 | 이유 |
|----------|------|------|
| **CRUD/동기화** | neomodel OGM | 편의성, Django ORM 스타일, 약간의 레이턴시 허용 |
| **조회/검색 (Agent)** | raw driver (neo4j_graphrag) | 실시간 응답, 최소 레이턴시, 음성 처리에 적합 |

**성능 순서**: raw driver > neomodel cypher_query > neomodel OGM

```python
# CRUD (동기화) - neomodel OGM
team = Team(id=str(team_id), name=name)
await team.save()

# 검색 (Agent) - neo4j_graphrag ToolsRetriever (raw driver)
results = await tools_retriever.search(query)  # 빠름!
```

## 3. 동기화 대상

### PostgreSQL → Neo4j 동기화

| PostgreSQL 테이블 | Neo4j 노드/관계 | 동기화 필드 |
|------------------|-----------------|-------------|
| users | User | id, name, email |
| teams | Team | id, name, description |
| meetings | Meeting | id, title, status, description, scheduled_at, started_at, ended_at |
| team_members | MEMBER_OF | user_id, team_id, role |
| meeting_participants | PARTICIPATED_IN | user_id, meeting_id, role |
| meetings.team_id | HOSTS | team_id → meeting_id |

### Neo4j 전용 (동기화 불필요)

| 노드 | 설명 |
|------|------|
| Agenda | 회의 안건 |
| Decision | 결정사항 (GT) |
| ActionItem | 액션아이템 |

| 관계 | 설명 |
|------|------|
| CONTAINS | Meeting → Agenda |
| HAS_DECISION | Agenda → Decision |
| SUPERSEDES | Decision → Decision (버전 관리) |
| TRIGGERS | Decision → ActionItem |
| APPROVED | User → Decision |
| ASSIGNED_TO | User → ActionItem |

## 4. 동기화 시점

| 이벤트 | PostgreSQL | Neo4j 동기화 |
|--------|------------|--------------|
| Team 생성 | INSERT | CREATE (:Team) |
| Team 수정 | UPDATE | SET team.name, team.description |
| Team 삭제 | DELETE | DETACH DELETE (t:Team) |
| User 생성 | INSERT | CREATE (:User) |
| Meeting 생성 | INSERT | CREATE (:Meeting), CREATE (:Team)-[:HOSTS]->(:Meeting) |
| 팀 멤버 추가 | INSERT | CREATE (:User)-[:MEMBER_OF]->(:Team) |
| 회의 참여 | INSERT | CREATE (:User)-[:PARTICIPATED_IN]->(:Meeting) |

## 5. 구현 패턴

### 서비스 레이어 동기화

```python
# backend/app/services/team_service.py
class TeamService:
    def __init__(self, db: AsyncSession, neo4j_repo: Neo4jSyncRepository):
        self.db = db
        self.neo4j_repo = neo4j_repo

    async def create_team(self, data: CreateTeamRequest, user_id: UUID) -> TeamResponse:
        # 1. PostgreSQL 먼저 (SSOT)
        team = Team(name=data.name, description=data.description, created_by=user_id)
        self.db.add(team)
        await self.db.flush()

        # 2. Neo4j 동기화 (실패해도 롤백 안함, 로깅 후 수동 복구)
        try:
            await self.neo4j_repo.create_team_node(
                team_id=str(team.id),
                name=team.name,
                description=team.description
            )
        except Exception as e:
            logger.error(f"Neo4j sync failed for team {team.id}: {e}")
            # 추후 재시도 큐에 추가 가능

        await self.db.commit()
        return TeamResponse.model_validate(team)
```

### Neo4j Sync Repository

```python
# backend/app/repositories/neo4j_sync_repository.py
class Neo4jSyncRepository:
    def __init__(self, driver):
        self.driver = driver

    async def create_team_node(self, team_id: str, name: str, description: str | None):
        query = '''
        MERGE (t:Team {id: $id})
        SET t.name = $name, t.description = $description
        '''
        async with self.driver.session() as session:
            await session.run(query, {
                "id": team_id,
                "name": name,
                "description": description
            })

    async def create_member_of_relation(self, user_id: str, team_id: str, role: str):
        query = '''
        MATCH (u:User {id: $user_id}), (t:Team {id: $team_id})
        MERGE (u)-[r:MEMBER_OF]->(t)
        SET r.role = $role
        '''
        async with self.driver.session() as session:
            await session.run(query, {
                "user_id": user_id,
                "team_id": team_id,
                "role": role
            })

    async def delete_team_node(self, team_id: str):
        query = '''
        MATCH (t:Team {id: $id})
        DETACH DELETE t
        '''
        async with self.driver.session() as session:
            await session.run(query, {"id": team_id})
```

## 6. 오류 처리

### 동기화 실패 시

1. **PostgreSQL 작업은 성공** (롤백하지 않음)
2. **오류 로깅** - 상세 에러 메시지 기록
3. **선택적: 재시도 큐에 추가** (ARQ worker 활용 가능)
4. **수동 복구 스크립트 제공**

### 데이터 불일치 복구

```python
# scripts/sync_all_to_neo4j.py
async def sync_all_to_neo4j():
    """전체 PostgreSQL 데이터를 Neo4j로 동기화"""
    async with get_db_session() as db:
        # 팀 동기화
        teams = await db.execute(select(Team))
        for team in teams.scalars():
            await neo4j_repo.upsert_team_node(team)

        # 사용자 동기화
        users = await db.execute(select(User))
        for user in users.scalars():
            await neo4j_repo.upsert_user_node(user)

        # 회의 동기화
        meetings = await db.execute(select(Meeting))
        for meeting in meetings.scalars():
            await neo4j_repo.upsert_meeting_node(meeting)

        # 관계 동기화
        team_members = await db.execute(select(TeamMember))
        for tm in team_members.scalars():
            await neo4j_repo.upsert_member_of_relation(tm)

        # ... 나머지 엔티티도 동일
```

## 7. 검증 방법

### 동기화 검증

```python
# Team 생성 후 Neo4j 노드 확인
team = await team_service.create_team(data, user_id)
neo4j_team = await neo4j_repo.get_team(str(team.id))
assert neo4j_team is not None
assert neo4j_team["name"] == team.name
```

### 일관성 체크 스크립트

```python
# scripts/check_consistency.py
async def check_consistency():
    """PostgreSQL과 Neo4j 간 데이터 일관성 검사"""
    # PostgreSQL 팀 ID 목록
    pg_team_ids = {str(t.id) for t in await db.execute(select(Team.id))}

    # Neo4j 팀 ID 목록
    neo4j_team_ids = await neo4j_repo.get_all_team_ids()

    # 불일치 확인
    only_in_pg = pg_team_ids - neo4j_team_ids
    only_in_neo4j = neo4j_team_ids - pg_team_ids

    if only_in_pg:
        logger.warning(f"Teams only in PostgreSQL: {only_in_pg}")
    if only_in_neo4j:
        logger.warning(f"Teams only in Neo4j: {only_in_neo4j}")
```

## 8. 참조

- 스키마: [neo4j-schema-setup.md](./neo4j-schema-setup.md)
- 사용 패턴: [neo4j-usage-patterns.md](./neo4j-usage-patterns.md)
- Docker 설정: [neo4j-docker-setup.md](./neo4j-docker-setup.md)
- Mocking 전략: [neo4j-mocking-strategy.md](./neo4j-mocking-strategy.md)
