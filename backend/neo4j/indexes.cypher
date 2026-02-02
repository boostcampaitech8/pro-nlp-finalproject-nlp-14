// MIT Neo4j 인덱스 정의
// 실행: make neo4j-init

// 검색용 인덱스
CREATE INDEX meeting_status IF NOT EXISTS FOR (m:Meeting) ON (m.status);
CREATE INDEX meeting_scheduled IF NOT EXISTS FOR (m:Meeting) ON (m.scheduled_at);
CREATE INDEX decision_status IF NOT EXISTS FOR (d:Decision) ON (d.status);
CREATE INDEX actionitem_status IF NOT EXISTS FOR (ai:ActionItem) ON (ai.status);
CREATE INDEX actionitem_due IF NOT EXISTS FOR (ai:ActionItem) ON (ai.due_date);
CREATE INDEX suggestion_created IF NOT EXISTS FOR (s:Suggestion) ON (s.created_at);
CREATE INDEX comment_created IF NOT EXISTS FOR (c:Comment) ON (c.created_at);

// 팀 기반 가시성 인덱스
CREATE INDEX meeting_team IF NOT EXISTS FOR (m:Meeting) ON (m.team_id);
CREATE INDEX agenda_team IF NOT EXISTS FOR (a:Agenda) ON (a.team_id);
CREATE INDEX decision_team IF NOT EXISTS FOR (d:Decision) ON (d.team_id);
CREATE INDEX actionitem_team IF NOT EXISTS FOR (ai:ActionItem) ON (ai.team_id);
CREATE INDEX suggestion_team IF NOT EXISTS FOR (s:Suggestion) ON (s.team_id);
CREATE INDEX comment_team IF NOT EXISTS FOR (c:Comment) ON (c.team_id);

// 전문 검색 인덱스
CREATE FULLTEXT INDEX meeting_search IF NOT EXISTS
FOR (m:Meeting) ON EACH [m.title, m.summary];

CREATE FULLTEXT INDEX decision_search IF NOT EXISTS
FOR (d:Decision) ON EACH [d.content, d.context];
