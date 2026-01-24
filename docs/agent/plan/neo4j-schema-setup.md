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

### 관계 타입

| Type | From | To | 속성 | 설명 |
|------|------|----|----|------|
| MEMBER_OF | User | Team | role | 팀 멤버십 |
| HOSTS | Team | Meeting | - | 팀이 회의 주관 |
| PARTICIPATED_IN | User | Meeting | role | 회의 참여 |
| CONTAINS | Meeting | Agenda | - | 회의에 안건 포함 |
| HAS_DECISION | Agenda | Decision | - | 안건의 결정사항 |
| REVIEWED_BY | User | Decision | status, responded_at | GT 승인 |
| SUPERSEDES | Decision | Decision | - | 결정 대체 (버전 관리) |
| TRIGGERS | Decision | ActionItem | - | 결정에서 액션아이템 파생 |
| ASSIGNED_TO | User | ActionItem | assigned_at | 액션아이템 할당 |

## 2. 제약조건 생성

```cypher
// 노드 고유성 제약조건
CREATE CONSTRAINT team_id IF NOT EXISTS FOR (t:Team) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT meeting_id IF NOT EXISTS FOR (m:Meeting) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT agenda_id IF NOT EXISTS FOR (a:Agenda) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT actionitem_id IF NOT EXISTS FOR (ai:ActionItem) REQUIRE ai.id IS UNIQUE;

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

// 전문 검색 인덱스 (선택)
CREATE FULLTEXT INDEX meeting_search IF NOT EXISTS
FOR (m:Meeting) ON EACH [m.title, m.summary];

CREATE FULLTEXT INDEX decision_search IF NOT EXISTS
FOR (d:Decision) ON EACH [d.content, d.context];
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
```cypher
// 1. 노드 생성 (순서 중요)
// Team 먼저
LOAD CSV WITH HEADERS FROM 'file:///000.csv' AS row
WITH row WHERE row.type = 'Team'
WITH row, apoc.convert.fromJsonMap(row.data) AS data
CREATE (t:Team {
  id: data.id,
  name: data.name,
  description: data.description
});

// User
LOAD CSV WITH HEADERS FROM 'file:///000.csv' AS row
WITH row WHERE row.type = 'User'
WITH row, apoc.convert.fromJsonMap(row.data) AS data
CREATE (u:User {
  id: data.id,
  email: data.email,
  name: data.name
});

// Meeting, Agenda, Decision, ActionItem도 동일한 패턴

// 2. 관계 생성 (노드 생성 후)
LOAD CSV WITH HEADERS FROM 'file:///000.csv' AS row
WITH row WHERE row.type = 'MEMBER_OF'
WITH row, apoc.convert.fromJsonMap(row.data) AS data
MATCH (u:User {id: data.from}), (t:Team {id: data.to})
CREATE (u)-[:MEMBER_OF {role: data.role}]->(t);

// 나머지 관계도 동일한 패턴
```

### 여러 CSV 파일 Import
```cypher
// 모든 CSV 파일에서 Team 노드 생성
UNWIND ['000', '001', '002', '003', '004'] AS fileNum
LOAD CSV WITH HEADERS FROM 'file:///' + fileNum + '.csv' AS row
WITH row WHERE row.type = 'Team'
WITH row, apoc.convert.fromJsonMap(row.data) AS data
MERGE (t:Team {id: data.id})
SET t.name = data.name, t.description = data.description;
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
- CSV 데이터: `data/augment/000.csv` ~ `018.csv`
- Import 스크립트: `data/augment/import.cypher`
- 조회 쿼리: `data/augment/view_cypher.md`
