// MIT Neo4j 인덱스 정의
// 실행: make neo4j-init

// 검색용 인덱스
CREATE INDEX meeting_status IF NOT EXISTS FOR (m:Meeting) ON (m.status);
CREATE INDEX meeting_scheduled IF NOT EXISTS FOR (m:Meeting) ON (m.scheduled_at);
CREATE INDEX decision_status IF NOT EXISTS FOR (d:Decision) ON (d.status);
CREATE INDEX actionitem_status IF NOT EXISTS FOR (ai:ActionItem) ON (ai.status);
CREATE INDEX actionitem_due IF NOT EXISTS FOR (ai:ActionItem) ON (ai.due_date);

// 전문 검색 인덱스
CREATE FULLTEXT INDEX meeting_search IF NOT EXISTS
FOR (m:Meeting) ON EACH [m.title, m.summary];

CREATE FULLTEXT INDEX decision_search IF NOT EXISTS
FOR (d:Decision) ON EACH [d.content, d.context];
