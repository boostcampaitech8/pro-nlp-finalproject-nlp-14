# Neo4j Schema Setup

MIT 그래프 데이터베이스 스키마 정의 및 데이터 구축

## 1. 스키마 개요

### 노드 타입

| Label | 설명 | 주요 속성 |
|-------|------|----------|
| Team | 팀/조직 | id, name, description |
| User | 사용자 | id, email, name |
| Meeting | 회의 | id, title, status, description, transcript, summary, scheduled_at, started_at, ended_at, created_at |
| Agenda | 안건 | id, topic, description, created_at |
| Decision | 결정사항 (GT) | id, content, status, context, created_at |
| ActionItem | 액션아이템 | id, title, description, due_date, status, created_at |
| Suggestion | 결정 수정 제안 | id, content, created_at |
| Comment | 결정에 대한 댓글 | id, content, created_at |

### 관계 타입

| Type | From | To | 속성 | 설명 |
|------|------|----|----|------|
| MEMBER_OF | User | Team | role | 팀 멤버십 |
| HOSTS | Team | Meeting | - | 팀이 회의 주관 |
| PARTICIPATED_IN | User | Meeting | role | 회의 참여 |
| CONTAINS | Meeting | Agenda | - | 회의에 안건 포함 |
| HAS_DECISION | Agenda | Decision | - | 안건의 결정사항 |
| REVIEWED | User | Decision | status, responded_at | GT 승인 |
| SUPERSEDES | Decision | Decision | - | 결정 대체 (버전 관리) |
| SUPERSEDED_BY | Decision | Decision | - | 원본 → 새 버전 관계 |
| TRIGGERS | Decision | ActionItem | - | 결정에서 액션아이템 파생 |
| ASSIGNED_TO | User | ActionItem | assigned_at | 액션아이템 할당 |
| SUGGESTS | User | Suggestion | - | 사용자가 수정 제안 작성 |
| CREATES | Suggestion | Decision | - | 제안이 새 Decision 생성 |
| COMMENTS | User | Comment | - | 사용자가 댓글 작성 |
| ON | Comment | Decision | - | 댓글이 Decision에 연결 |
| REPLY_TO | Comment | Comment | - | 대댓글 관계 |

## 2. 제약조건 생성

```cypher
// 노드 고유성 제약조건
CREATE CONSTRAINT team_id IF NOT EXISTS FOR (t:Team) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT meeting_id IF NOT EXISTS FOR (m:Meeting) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT agenda_id IF NOT EXISTS FOR (a:Agenda) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT actionitem_id IF NOT EXISTS FOR (ai:ActionItem) REQUIRE ai.id IS UNIQUE;
CREATE CONSTRAINT suggestion_id IF NOT EXISTS FOR (s:Suggestion) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT comment_id IF NOT EXISTS FOR (c:Comment) REQUIRE c.id IS UNIQUE;

// 이메일 고유성
CREATE CONSTRAINT user_email IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE;
```

## 3. 인덱스 생성

```cypher
// 검색용 인덱스
CREATE INDEX meeting_status IF NOT EXISTS FOR (m:Meeting) ON (m.status);
CREATE INDEX meeting_scheduled IF NOT EXISTS FOR (m:Meeting) ON (m.scheduled_at);
CREATE INDEX decision_status IF NOT EXISTS FOR (d:Decision) ON (d.status);
CREATE INDEX actionitem_status IF NOT EXISTS FOR (ai:ActionItem) ON (ai.status);
CREATE INDEX actionitem_due IF NOT EXISTS FOR (ai:ActionItem) ON (ai.due_date);
CREATE INDEX suggestion_created IF NOT EXISTS FOR (s:Suggestion) ON (s.created_at);
CREATE INDEX comment_created IF NOT EXISTS FOR (c:Comment) ON (c.created_at);

// 전문 검색 인덱스 (선택)
CREATE FULLTEXT INDEX meeting_search IF NOT EXISTS
FOR (m:Meeting) ON EACH [m.title, m.summary];

CREATE FULLTEXT INDEX decision_search IF NOT EXISTS
FOR (d:Decision) ON EACH [d.content, d.context];

CREATE FULLTEXT INDEX comment_search IF NOT EXISTS
FOR (c:Comment) ON EACH [c.content];
```

## 4. 데이터 Import

### 사전 준비
CSV 파일이 Neo4j import 디렉토리에 마운트되어 있어야 함.
(docker-compose.yml에서 `../data/augment:/var/lib/neo4j/import:ro` 설정)

### Import 실행

#### 방법 1: Neo4j Browser에서 직접 실행
1. http://localhost:7474 접속
2. `data/augment/import.cypher` 내용을 복사하여 실행

#### 방법 2: cypher-shell 사용
```bash
# 컨테이너에서 실행
docker exec -i mit-neo4j cypher-shell -u neo4j -p ${NEO4J_PASSWORD} < data/augment/import.cypher
```

#### 방법 3: 단계별 실행

CSV 파일은 노드/관계 타입별로 분리되어 있음 (`nodes/`, `relationships/` 폴더).

```cypher
// 1. 노드 생성 (순서 중요)

// Teams
LOAD CSV WITH HEADERS FROM 'file:///nodes/teams.csv' AS row
CREATE (t:Team {id: row.id, name: row.name, description: row.description});

// Users
LOAD CSV WITH HEADERS FROM 'file:///nodes/users.csv' AS row
CREATE (u:User {id: row.id, email: row.email, name: row.name});

// Meetings
LOAD CSV WITH HEADERS FROM 'file:///nodes/meetings.csv' AS row
CREATE (m:Meeting {
  id: row.id,
  title: row.title,
  status: row.status,
  description: row.description,
  transcript: row.transcript,
  summary: row.summary,
  scheduled_at: CASE WHEN row.scheduled_at IS NOT NULL THEN datetime(row.scheduled_at) ELSE null END,
  started_at: CASE WHEN row.started_at IS NOT NULL THEN datetime(row.started_at) ELSE null END,
  ended_at: CASE WHEN row.ended_at IS NOT NULL THEN datetime(row.ended_at) ELSE null END,
  created_at: datetime(row.created_at)
});

// Agendas, Decisions, ActionItems도 동일한 패턴

// 2. 관계 생성 (노드 생성 후)

// MEMBER_OF
LOAD CSV WITH HEADERS FROM 'file:///relationships/member_of.csv' AS row
MATCH (u:User {id: row.from_id}), (t:Team {id: row.to_id})
CREATE (u)-[:MEMBER_OF {role: row.role}]->(t);

// HOSTS
LOAD CSV WITH HEADERS FROM 'file:///relationships/hosts.csv' AS row
MATCH (t:Team {id: row.from_id}), (m:Meeting {id: row.to_id})
CREATE (t)-[:HOSTS]->(m);

// 나머지 관계도 동일한 패턴 (participated_in, contains, has_decision, triggers, assigned_to)
```

## 5. 데이터 확인

```cypher
// 노드 수 확인
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS count
ORDER BY count DESC;

// 관계 수 확인
MATCH ()-[r]->()
RETURN type(r) AS type, count(*) AS count
ORDER BY count DESC;

// 스키마 시각화
CALL db.schema.visualization();

// 제약조건 확인
SHOW CONSTRAINTS;

// 인덱스 확인
SHOW INDEXES;
```

## 6. 참조 파일
- 노드 CSV: `data/augment/nodes/` (teams.csv, users.csv, meetings.csv, ...)
- 관계 CSV: `data/augment/relationships/` (member_of.csv, hosts.csv, ...)
- Import 스크립트: `data/augment/import.cypher`
- 조회 쿼리: `data/augment/view_cypher.md`

## 7. 관계 다이어그램

### Suggestion 흐름
```
User ─SUGGESTS─> Suggestion ─CREATES─> Decision (새 버전, status='draft')
                                             │
Decision (원본) ─SUPERSEDED_BY─────────────>─┘
```

### Comment 흐름
```
User ─COMMENTS─> Comment ─ON─> Decision
                    │
                    └──REPLY_TO──> Comment (대댓글)
```

### 전체 Minutes View 구조
```
Meeting ─CONTAINS─> Agenda ─HAS_DECISION─> Decision
                                               │
                                               ├─> Suggestion (via SUPERSEDED_BY -> CREATES)
                                               ├─> Comment (via ON)
                                               └─> ActionItem (via TRIGGERS)
```
