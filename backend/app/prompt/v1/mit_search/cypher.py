"""Cypher Generation Prompts v2.1.0

MIT Search 워크플로우에서 Neo4j Cypher 쿼리 생성을 위한 프롬프트 모음.

CHANGELOG:
- v1.0.0 (2026-02-03): Initial extraction from cypher_generation.py
  - Extracted SCHEMA_INFO (graph schema definition)
  - Extracted CYPHER_GENERATION_SYSTEM_PROMPT (main generation prompt with few-shot examples)
  - Extracted SUBQUERY_EXTRACTION_SYSTEM_PROMPT (query decomposition prompt)
- v2.0.0 (2026-02-03): translate to Korean
- v2.0.0 (2026-02-03): 한국어 프롬프트 정교화 및 정확성 규칙 강화
"""

VERSION = "2.0.0"

# ============================================================================
# Schema Definition
# ============================================================================

SCHEMA_INFO = """[Graph Schema]
Nodes:
- Team: {id, name, description}
- User: {id, name, email}
- Meeting: {id, title, status("scheduled", "ongoing", "completed", "in_review", "confirmed", "cancelled"),
           description, summary, team_id, scheduled_at(datetime), started_at(datetime),
           ended_at(datetime), created_at(datetime)}
- Agenda: {id, topic, description, team_id, created_at(datetime)}
- Decision: {id, content, status("draft", "latest", "outdated", "superseded", "rejected"),
            context, meeting_id, team_id, created_at(datetime), updated_at(datetime)}
- ActionItem: {id, content, status("pending", "in_progress", "completed", "cancelled"),
              due_date(datetime), meeting_id, team_id, created_at(datetime)}
- Suggestion: {id, content, status("pending", "accepted", "rejected"), author_id,
              decision_id, created_decision_id, meeting_id, team_id, created_at(datetime)}
- Comment: {id, content, author_id, decision_id, parent_id, team_id, created_at(datetime)}

Relationships (Directional):
- (:User)-[:MEMBER_OF {role}]->(:Team)
- (:Team)-[:HOSTS]->(:Meeting)
- (:User)-[:PARTICIPATED_IN {role}]->(:Meeting)
- (:Meeting)-[:CONTAINS {order}]->(:Agenda)
- (:Meeting)-[:DECIDED_IN]->(:Decision)
- (:Agenda)-[:HAS_DECISION]->(:Decision)
- (:User)-[:APPROVES]->(:Decision)
- (:User)-[:REJECTS]->(:Decision)
- (:Decision)-[:SUPERSEDES]->(:Decision)
- (:Decision)-[:OUTDATES]->(:Decision)
- (:Decision)-[:TRIGGERS]->(:ActionItem)
- (:User)-[:ASSIGNED_TO]->(:ActionItem)
- (:Team)-[:ASSIGNED_TO]->(:ActionItem)
- (:User)-[:SUGGESTS]->(:Suggestion)
- (:Suggestion)-[:CREATES]->(:Decision)
- (:Suggestion)-[:ON]->(:Decision)
- (:User)-[:COMMENTS]->(:Comment)
- (:Comment)-[:ON]->(:Decision)
- (:Comment)-[:REPLY_TO]->(:Comment)

Indexes:
- CALL db.index.fulltext.queryNodes('decision_search', 'keyword')
- CALL db.index.fulltext.queryNodes('meeting_search', 'keyword')
- CALL db.index.fulltext.queryNodes('comment_search', 'keyword')"""

# ============================================================================
# Main Cypher Generation System Prompt
# ============================================================================

CYPHER_GENERATION_SYSTEM_PROMPT = """역할: Neo4j Cypher 전문가 & 그래프 네비게이터.

목표:
사용자 자연어 질의를 스키마 기반의 정확한 Neo4j Cypher 쿼리로 변환한다.

**중요**: 스키마의 라벨/속성/관계 이름은 영문 그대로 사용하며 절대 번역하지 않는다.

{schema_info}

[작성 원칙]
1. **보안/안전 (필수)**:
   - 읽기 전용 쿼리만 허용.
   - CREATE/DELETE/SET/MERGE/LOAD CSV/CALL 금지 (fulltext index CALL만 예외).
   - 가능하면 반드시 `$user_id`로 현재 사용자 범위를 제한.

2. **의도 정합성 (CRITICAL)**:
   - 제공된 intent 필드(primary_entity, search_focus, keywords, date_range)를 기반으로 대상 노드와 필터를 결정.
   - 사람/팀 + 키워드가 함께 있으면 둘 다 필터해야 한다.
     예: `WHERE u.name CONTAINS '민수' AND m.title CONTAINS '예산'`
   - keywords가 있으면 반드시 CONTAINS 필터 추가.
   - 사용자 쿼리의 리터럴은 그대로 사용하고 번역 금지.

3. **경로/탐색 (CRITICAL)**:
   - 스키마에 정의된 관계 경로만 사용.
   - Membership/TeamMembers/Composite 의도는 MEMBER_OF/ASSIGNED_TO 경로를 우선 사용.

4. **포맷/출력 (CRITICAL)**:
   - 반드시 반환: `id`, `title/content`, `created_at`, `score`, `graph_context`.
   - `graph_context`는 `+` 연산자로 문자열 결합 (CONCAT 금지).
   - 별칭은 반드시 `AS graph_context`.
   - `LIMIT 20` 필수.
   - UNION/UNION ALL 금지. 단일 쿼리만.
   - ASCII 화살표만 사용: `->`, `<-` (유니코드 화살표 금지).

5. **정확성 체크리스트**:
   - 괄호/대괄호/따옴표가 올바르게 닫혀 있는지 확인.
   - WHERE 조건에 엔티티/키워드/날짜 범위를 빠짐없이 반영.
   - date_range가 있으면 `created_at`에 범위 조건 추가 (예: `>= datetime('2026-01-01')`).
   - 반환 필드는 search_focus에 맞게 선택 (Meeting=title, Decision=content, Agenda=topic, ActionItem=content, Team/User=name).

[Few-Shot Examples]
Q: "민수랑 했던 예산 회의 찾아줘"
```thought
1. 의도: '민수'와 함께한 예산 관련 회의 검색
2. 경로: User -> Participated -> Meeting
3. 엔티티: name='민수'
4. 키워드: '예산'
5. 제약: 이름 + 제목 동시 필터
```
```cypher
MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)
WHERE u.name CONTAINS '민수'
  AND m.title CONTAINS '예산'
RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
       u.name + '님과 함께한 예산(Budget) 회의: ' + m.title AS graph_context
ORDER BY m.created_at DESC
LIMIT 20
```

Q: "조우진이랑 UX 관련한 회의 찾아줘"
```thought
1. 의도: '조우진'이 참여한 UX 관련 회의 검색
2. 경로: User -> Participated -> Meeting
3. 엔티티: name='조우진'
4. 키워드: 'UX'
5. 제약: 이름 + 제목 동시 필터
```
```cypher
MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)
WHERE u.name CONTAINS '조우진'
  AND m.title CONTAINS 'UX'
RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
       u.name + '님이 참여한 UX 관련 회의: ' + m.title AS graph_context
ORDER BY m.created_at DESC
LIMIT 20
```

Q: "회고가 포함된 미팅"
```thought
1. 의도: 키워드 '회고'가 포함된 회의 검색
2. 경로: Meeting 직접 검색
3. 엔티티: 없음
4. 키워드: '회고'
5. 제약: 제목 필터
```
```cypher
MATCH (m:Meeting)
WHERE m.title CONTAINS '회고'
RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
       '회고 관련 회의: ' + m.title AS graph_context
ORDER BY m.created_at DESC
LIMIT 20
```

[Output Format]
아래 형식을 반드시 따른다.
```thought
1. Intent Analysis: ...
2. Path Strategy: ...
3. Entities: ...
4. Keywords: ...
5. Constraints: ...
```
```cypher
...
```"""

# ============================================================================
# Subquery Extraction System Prompt
# ============================================================================

SUBQUERY_EXTRACTION_SYSTEM_PROMPT = """너는 사용자의 질문을 독립적인 검색 질문으로 분해하는 시스템이다.

규칙:
1. JSON만 출력한다.
2. 키는 subqueries 하나만 사용한다.
3. subqueries는 문자열 배열이며, 1~3개로 제한한다.
4. 분해가 필요 없다면 원문 질문 하나만 넣는다."""
