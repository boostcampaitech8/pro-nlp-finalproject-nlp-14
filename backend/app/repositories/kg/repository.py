"""Neo4j KG Repository

Raw Cypher 기반 Knowledge Graph 저장소.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from neo4j.time import DateTime as Neo4jDateTime

from app.models.kg import (
    KGActionItem,
    KGAgenda,
    KGComment,
    KGDecision,
    KGMeeting,
    KGMinutes,
    KGMinutesActionItem,
    KGMinutesDecision,
    KGSuggestion,
)
from neo4j import AsyncDriver


def _convert_neo4j_datetime(value: Any) -> datetime:
    """Neo4j DateTime을 Python datetime으로 변환"""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, Neo4jDateTime):
        return value.to_native()
    if isinstance(value, datetime):
        return value
    return datetime.now(timezone.utc)


def _build_comment_tree(flat_comments: list[dict]) -> list[dict]:
    """Flat comment list를 nested tree로 변환 (무제한 depth 지원)

    Args:
        flat_comments: parent_id를 포함한 flat comment 리스트

    Returns:
        replies가 재귀적으로 중첩된 top-level comment 리스트
    """
    # 1. ID → comment dict 매핑 (replies 필드 초기화)
    comment_map = {c["id"]: {**c, "replies": []} for c in flat_comments}

    # 2. Tree 구성
    root_comments = []
    for c in flat_comments:
        parent_id = c.get("parent_id")
        comment = comment_map[c["id"]]

        # parent_id는 응답에서 제거
        if "parent_id" in comment:
            del comment["parent_id"]

        if parent_id is None:
            # Top-level comment
            root_comments.append(comment)
        elif parent_id in comment_map:
            # Reply - parent의 replies에 추가
            comment_map[parent_id]["replies"].append(comment)

    return root_comments


class KGRepository:
    """Neo4j KG Repository - Raw Cypher"""

    def __init__(self, driver: AsyncDriver):
        self.driver = driver

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        """읽기 쿼리 실행"""
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            return [dict(record) async for record in result]

    async def _execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        """쓰기 쿼리 실행"""

        async def _write_tx(tx):
            result = await tx.run(query, parameters or {})
            return [dict(record) async for record in result]

        async with self.driver.session() as session:
            return await session.execute_write(_write_tx)

    # =========================================================================
    # Meeting - 회의
    # =========================================================================

    async def update_meeting(self, meeting_id: str, data: dict) -> KGMeeting:
        """회의 업데이트 (임베딩, 요약 등)"""
        set_clauses = []
        params = {"meeting_id": meeting_id}
        for key, value in data.items():
            set_clauses.append(f"m.{key} = ${key}")
            params[key] = value

        query = f"""
        MATCH (m:Meeting {{id: $meeting_id}})
        SET {', '.join(set_clauses)}
        RETURN m
        """
        records = await self._execute_write(query, params)
        if not records:
            raise ValueError(f"Meeting not found: {meeting_id}")

        return await self.get_meeting(meeting_id)  # type: ignore

    async def get_meeting(self, meeting_id: str) -> KGMeeting | None:
        """회의 조회 (팀, 참여자 포함)"""
        query = """
        MATCH (m:Meeting {id: $meeting_id})
        OPTIONAL MATCH (t:Team)-[:HOSTS]->(m)
        OPTIONAL MATCH (u:User)-[:PARTICIPATED_IN]->(m)
        RETURN m, t, collect(DISTINCT u.id) as participant_ids
        """
        records = await self._execute_read(query, {"meeting_id": meeting_id})
        if not records:
            return None

        record = records[0]
        m = dict(record["m"])
        t = dict(record["t"]) if record["t"] else {}

        created_at_raw = m.get("created_at")
        created_at = _convert_neo4j_datetime(created_at_raw) if created_at_raw else None

        return KGMeeting(
            id=m["id"],
            title=m.get("title", ""),
            status=m.get("status", ""),
            team_id=t.get("id"),
            team_name=t.get("name"),
            participant_ids=record["participant_ids"] or [],
            created_at=created_at,
        )

    # =========================================================================
    # Agenda - 아젠다
    # =========================================================================

    async def get_agenda(self, meeting_id: str) -> list[KGAgenda]:
        """회의의 아젠다 목록 조회"""
        query = """
        MATCH (m:Meeting {id: $meeting_id})-[:CONTAINS]->(a:Agenda)
        RETURN a
        ORDER BY a.order
        """
        records = await self._execute_read(query, {"meeting_id": meeting_id})
        return [
            KGAgenda(
                id=dict(r["a"])["id"],
                topic=dict(r["a"]).get("topic", ""),
                description=dict(r["a"]).get("description"),
                order=dict(r["a"]).get("order", 0),
                meeting_id=meeting_id,
            )
            for r in records
        ]

    # =========================================================================
    # Minutes - 회의록
    # =========================================================================

    async def create_minutes(
        self,
        meeting_id: str,
        summary: str,
        agendas: list[dict],
    ) -> KGMinutes:
        """회의록 생성 (원홉 - Minutes 노드 없음)

        Meeting-Agenda-Decision을 한 번에 생성:
        - Meeting.summary 업데이트
        - Meeting -[CONTAINS]-> Agenda 생성
        - Agenda -[HAS_DECISION]-> Decision 생성

        Args:
            meeting_id: 회의 ID
            summary: 회의 요약
            agendas: [{topic, description, decision: {content, context} | null}]

        Returns:
            KGMinutes (Projection - 생성된 데이터로 구성)
        """
        now = datetime.now(timezone.utc).isoformat()

        query = """
        MATCH (m:Meeting {id: $meeting_id})

        // 1. Meeting summary 업데이트
        SET m.summary = $summary

        // 2. Agenda + Decision 생성 (UNWIND)
        WITH m
        UNWIND range(0, size($agendas) - 1) AS idx
        WITH m, $agendas[idx] AS agenda_data, idx
        CREATE (a:Agenda {
            id: 'agenda-' + randomUUID(),
            topic: agenda_data.topic,
            description: coalesce(agenda_data.description, ''),
            order: idx,
            created_at: datetime($created_at)
        })
        CREATE (m)-[:CONTAINS]->(a)

        // 3. Decision 생성 (decision이 있는 경우만)
        // meeting_id 추가 + DECIDED_IN 관계 생성
        WITH m, a, agenda_data
        WHERE agenda_data.decision IS NOT NULL
        CREATE (d:Decision {
            id: 'decision-' + randomUUID(),
            content: agenda_data.decision.content,
            context: coalesce(agenda_data.decision.context, ''),
            status: 'draft',
            meeting_id: m.id,
            created_at: datetime($created_at)
        })
        CREATE (a)-[:HAS_DECISION]->(d)
        CREATE (m)-[:DECIDED_IN]->(d)

        RETURN m.id AS meeting_id,
               collect(DISTINCT a.id) AS agenda_ids,
               collect(DISTINCT d.id) AS decision_ids
        """
        await self._execute_write(
            query,
            {
                "meeting_id": meeting_id,
                "summary": summary,
                "created_at": now,
                "agendas": agendas,
            },
        )

        # Projection으로 조회하여 반환
        return await self.get_minutes(meeting_id)  # type: ignore

    async def get_minutes(self, meeting_id: str) -> KGMinutes | None:
        """회의록 조회 (Projection - Meeting + Agenda + Decision 조합)

        Minutes는 별도 노드가 아닌, 세 노드의 관계를 조합한 뷰
        """
        query = """
        MATCH (m:Meeting {id: $meeting_id})
        OPTIONAL MATCH (m)-[:CONTAINS]->(a:Agenda)
        OPTIONAL MATCH (a)-[:HAS_DECISION]->(d:Decision)
        OPTIONAL MATCH (d)-[:TRIGGERS]->(ai:ActionItem)
        OPTIONAL MATCH (ai)<-[:ASSIGNED_TO]-(assignee:User)
        RETURN m,
               collect(DISTINCT {
                   id: d.id,
                   content: d.content,
                   context: d.context,
                   agenda_topic: a.topic
               }) as decisions,
               collect(DISTINCT {
                   id: ai.id,
                   title: ai.title,
                   description: ai.description,
                   assignee: assignee.name,
                   due_date: ai.due_date
               }) as action_items
        """
        records = await self._execute_read(query, {"meeting_id": meeting_id})
        if not records:
            return None

        record = records[0]
        m = dict(record["m"])

        decisions = [
            KGMinutesDecision(**d)
            for d in record["decisions"]
            if d.get("id") is not None
        ]
        action_items = [
            KGMinutesActionItem(**ai)
            for ai in record["action_items"]
            if ai.get("id") is not None
        ]

        # Projection: Meeting + Agenda + Decision -> KGMinutes
        return KGMinutes(
            id=f"minutes-{meeting_id}",  # 가상 ID (실제 노드 아님)
            meeting_id=meeting_id,
            summary=m.get("summary", ""),
            created_at=_convert_neo4j_datetime(m.get("created_at")),
            decisions=decisions,
            action_items=action_items,
        )

    # =========================================================================
    # Decision - 결정사항
    # =========================================================================

    # --- 상태 변경 (승인/거절/머지) ---

    async def reject_decision(self, decision_id: str, user_id: str) -> bool:
        """결정 거절 (REJECTED_BY 관계 생성)

        Returns:
            bool: 거절 성공 여부 (decision과 user가 존재하면 True)
        """
        query = """
        MATCH (d:Decision {id: $decision_id})
        MATCH (u:User {id: $user_id})
        MERGE (u)-[:REJECTED_BY]->(d)
        RETURN d.id as decision_id
        """
        records = await self._execute_write(
            query, {"decision_id": decision_id, "user_id": user_id}
        )
        return len(records) > 0

    async def merge_decision(self, decision_id: str) -> bool:
        """결정 승격 (draft -> latest)

        동일 Agenda의 기존 latest Decision은 outdated로 변경됨.
        새 latest -[:SUPERSEDES]-> 기존 latest 관계 생성.

        Returns:
            bool: 승격 성공 여부 (decision이 존재하면 True)
        """
        now = datetime.now(timezone.utc).isoformat()

        query = """
        MATCH (d:Decision {id: $decision_id})

        // 1. 동일 Agenda의 기존 latest -> outdated + OUTDATES 관계
        OPTIONAL MATCH (d)<-[:HAS_DECISION]-(a:Agenda)-[:HAS_DECISION]->(old:Decision)
        WHERE old.status = 'latest' AND old.id <> $decision_id
        SET old.status = 'outdated', old.updated_at = datetime($now)
        // OUTDATES 관계가 없으면 생성 (GT 변화 추적)
        FOREACH (_ IN CASE WHEN old IS NOT NULL THEN [1] ELSE [] END |
            MERGE (d)-[:OUTDATES]->(old)
        )

        // 2. 현재 Decision -> latest
        WITH d
        SET d.status = 'latest', d.approved_at = datetime(), d.updated_at = datetime($now)
        RETURN d.id as decision_id
        """
        records = await self._execute_write(query, {
            "decision_id": decision_id,
            "now": now,
        })
        return len(records) > 0

    async def approve_and_merge_if_complete(
        self, decision_id: str, user_id: str
    ) -> dict:
        """결정 승인 + 전원 승인 시 자동 승격 (원자적 트랜잭션)

        단일 Cypher 쿼리로 승인 관계 생성, 전원 승인 확인, latest 승격을 처리.
        Race condition 없이 원자적으로 처리됨.
        전원 승인 시 동일 Agenda의 기존 latest Decision은 outdated로 변경됨.
        새 latest -[:SUPERSEDES]-> 기존 latest 관계 생성.

        Returns:
            {
                "approved": bool,       # 승인 성공 여부
                "merged": bool,         # latest 승격 여부
                "status": str,          # 최종 상태
                "approvers_count": int,
                "participants_count": int,
            }
        """
        now = datetime.now(timezone.utc).isoformat()

        query = """
        MATCH (d:Decision {id: $decision_id})
        MATCH (u:User {id: $user_id})

        // 1. 승인 관계 생성 (MERGE로 중복 방지)
        MERGE (u)-[:APPROVED_BY]->(d)

        // 2. 참여자 수와 승인자 수 계산
        WITH d
        MATCH (d)<-[:HAS_DECISION]-(a:Agenda)<-[:CONTAINS]-(m:Meeting)
        // 참여자가 Neo4j에 동기화되지 않았을 수 있으므로 OPTIONAL MATCH 사용
        OPTIONAL MATCH (participant:User)-[:PARTICIPATED_IN]->(m)
        WITH d, a, [p IN collect(DISTINCT participant.id) WHERE p IS NOT NULL] as participants

        OPTIONAL MATCH (approver:User)-[:APPROVED_BY]->(d)
        WITH d, a, participants, collect(DISTINCT approver.id) as approvers

        // 3. 전원 승인 시: 기존 latest -> outdated + OUTDATES 관계
        // 참여자가 없으면 (p_count = 0) 자동 승격하지 않음 (데이터 동기화 필요)
        WITH d, a, participants, approvers,
             size(participants) as p_count,
             size(approvers) as a_count
        OPTIONAL MATCH (a)-[:HAS_DECISION]->(old:Decision)
        WHERE old.status = 'latest' AND old.id <> d.id AND p_count > 0 AND p_count = a_count
        SET old.status = 'outdated', old.updated_at = datetime($now)
        // OUTDATES 관계 생성 (GT 변화 추적)
        FOREACH (_ IN CASE WHEN old IS NOT NULL AND p_count > 0 AND p_count = a_count THEN [1] ELSE [] END |
            MERGE (d)-[:OUTDATES]->(old)
        )

        // 4. 전원 승인 시: 현재 Decision -> latest
        // 참여자가 없으면 자동 승격하지 않음
        WITH d, participants, approvers, p_count, a_count
        SET d.status = CASE
            WHEN p_count > 0 AND p_count = a_count THEN 'latest'
            ELSE d.status
        END,
        d.approved_at = CASE
            WHEN p_count > 0 AND p_count = a_count THEN datetime()
            ELSE d.approved_at
        END,
        d.updated_at = CASE
            WHEN p_count > 0 AND p_count = a_count THEN datetime($now)
            ELSE d.updated_at
        END

        RETURN d.id as decision_id,
               d.status as status,
               p_count as participants_count,
               a_count as approvers_count,
               p_count > 0 AND p_count = a_count as merged
        """
        records = await self._execute_write(
            query, {"decision_id": decision_id, "user_id": user_id, "now": now}
        )

        if not records:
            return {"approved": False, "merged": False, "status": "not_found"}

        record = records[0]
        return {
            "approved": True,
            "merged": record["merged"],
            "status": record["status"],
            "approvers_count": record["approvers_count"],
            "participants_count": record["participants_count"],
        }

    # --- 조회 ---

    async def get_decision(self, decision_id: str) -> KGDecision | None:
        """결정사항 조회"""
        query = """
        MATCH (d:Decision {id: $decision_id})
        OPTIONAL MATCH (d)<-[:HAS_DECISION]-(a:Agenda)<-[:CONTAINS]-(m:Meeting)
        OPTIONAL MATCH (approver:User)-[:APPROVED_BY]->(d)
        OPTIONAL MATCH (rejector:User)-[:REJECTED_BY]->(d)
        OPTIONAL MATCH (d)-[:SUPERSEDES]->(prev:Decision)
        RETURN d, a, m,
               collect(DISTINCT approver.id) as approvers,
               collect(DISTINCT rejector.id) as rejectors,
               prev.id as supersedes_id
        """
        records = await self._execute_read(query, {"decision_id": decision_id})
        if not records:
            return None

        record = records[0]
        d = dict(record["d"])
        a = dict(record["a"]) if record["a"] else {}
        m = dict(record["m"]) if record["m"] else {}

        return KGDecision(
            id=d["id"],
            content=d.get("content", ""),
            status=d.get("status", "draft"),
            context=d.get("context"),
            meeting_id=d.get("meeting_id"),
            created_at=_convert_neo4j_datetime(d.get("created_at")),
            updated_at=_convert_neo4j_datetime(d.get("updated_at")) if d.get("updated_at") else None,
            agenda_id=a.get("id"),
            agenda_topic=a.get("topic"),
            meeting_title=m.get("title"),
            approvers=[aid for aid in record["approvers"] if aid],
            rejectors=[rid for rid in record["rejectors"] if rid],
            supersedes_id=record["supersedes_id"],
        )

    async def is_all_participants_approved(self, decision_id: str) -> bool:
        """모든 참여자 승인 여부 확인"""
        query = """
        MATCH (d:Decision {id: $decision_id})<-[:HAS_DECISION]-(a:Agenda)
              <-[:CONTAINS]-(m:Meeting)
        MATCH (u:User)-[:PARTICIPATED_IN]->(m)
        WITH d, collect(DISTINCT u.id) as participants
        OPTIONAL MATCH (approver:User)-[:APPROVED_BY]->(d)
        WITH participants, collect(DISTINCT approver.id) as approvers
        RETURN size(participants) = size(approvers) as all_approved
        """
        records = await self._execute_read(query, {"decision_id": decision_id})
        if not records:
            return False
        return records[0].get("all_approved", False)

    # =========================================================================
    # ActionItem - 액션아이템
    # =========================================================================

    async def create_action_items_batch(
        self,
        decision_id: str,
        action_items: list[dict],
    ) -> list[str]:
        """ActionItem 일괄 생성 + TRIGGERS + ASSIGNED_TO 관계

        Args:
            decision_id: 연결할 Decision ID
            action_items: [{"id", "title", "description", "due_date", "assignee_id"}]

        Returns:
            생성된 ActionItem ID 목록
        """
        if not action_items:
            return []

        now = datetime.now(timezone.utc).isoformat()

        # UUID 미리 생성
        for item in action_items:
            if "id" not in item:
                item["id"] = f"action-{uuid4()}"

        query = """
        MATCH (d:Decision {id: $decision_id})

        UNWIND $items AS item
        CREATE (ai:ActionItem {
            id: item.id,
            title: item.title,
            description: coalesce(item.description, ''),
            due_date: CASE WHEN item.due_date IS NOT NULL
                           THEN datetime(item.due_date)
                           ELSE null END,
            status: 'pending',
            created_at: datetime($created_at)
        })
        CREATE (d)-[:TRIGGERS]->(ai)

        // ASSIGNED_TO 관계 (assignee_id가 있는 경우)
        WITH ai, item
        OPTIONAL MATCH (u:User {id: item.assignee_id})
        FOREACH (_ IN CASE WHEN u IS NOT NULL THEN [1] ELSE [] END |
            CREATE (u)-[:ASSIGNED_TO {assigned_at: datetime($created_at)}]->(ai)
        )

        RETURN collect(ai.id) as action_ids
        """

        records = await self._execute_write(
            query,
            {
                "decision_id": decision_id,
                "items": action_items,
                "created_at": now,
            },
        )

        if not records:
            return []

        return records[0].get("action_ids", [])

    # =========================================================================
    # Suggestion - 제안
    # =========================================================================

    async def create_suggestion(
        self, decision_id: str, user_id: str, content: str, meeting_id: str
    ) -> "KGSuggestion":
        """Suggestion 생성 + 즉시 draft Decision 생성

        워크플로우:
        1. Suggestion 노드 생성 (status: 'pending')
        2. 새 draft Decision 즉시 생성
        3. 기존 draft Decision → superseded
        4. 새 Decision -[:SUPERSEDES]-> 기존 Decision

        Args:
            decision_id: 원본 Decision ID
            user_id: 작성자 ID
            content: Suggestion 내용
            meeting_id: Suggestion이 생성되는 Meeting ID (스코프)
        """
        from app.models.kg import KGSuggestion

        now = datetime.now(timezone.utc).isoformat()
        suggestion_id = f"suggestion-{uuid4()}"
        new_decision_id = f"decision-{uuid4()}"

        query = """
        MATCH (original:Decision {id: $decision_id})
        MATCH (u:User {id: $user_id})
        MATCH (m:Meeting {id: $meeting_id})
        MATCH (a:Agenda)-[:HAS_DECISION]->(original)

        // 1. Suggestion 노드 생성
        CREATE (s:Suggestion {
            id: $suggestion_id,
            content: $content,
            status: 'pending',
            meeting_id: $meeting_id,
            created_at: datetime($created_at)
        })
        CREATE (u)-[:SUGGESTS]->(s)
        CREATE (s)-[:ON]->(original)

        // 2. 새 draft Decision 즉시 생성
        CREATE (nd:Decision {
            id: $new_decision_id,
            content: $content,
            context: coalesce(original.context, ''),
            status: 'draft',
            meeting_id: $meeting_id,
            created_at: datetime($created_at)
        })
        CREATE (a)-[:HAS_DECISION]->(nd)
        CREATE (m)-[:DECIDED_IN]->(nd)
        CREATE (s)-[:CREATES]->(nd)
        CREATE (nd)-[:SUPERSEDES]->(original)

        // 3. 같은 Meeting 스코프의 기존 draft → superseded
        WITH s, nd, original, a
        OPTIONAL MATCH (a)-[:HAS_DECISION]->(old_draft:Decision)
        WHERE old_draft.status = 'draft'
          AND old_draft.meeting_id = $meeting_id
          AND old_draft.id <> nd.id
        SET old_draft.status = 'superseded', old_draft.updated_at = datetime($created_at)

        RETURN s.id as id, $content as content, $user_id as author_id,
               s.status as status, nd.id as created_decision_id,
               $decision_id as decision_id, $meeting_id as meeting_id,
               s.created_at as created_at
        """
        records = await self._execute_write(query, {
            "decision_id": decision_id,
            "user_id": user_id,
            "content": content,
            "meeting_id": meeting_id,
            "suggestion_id": suggestion_id,
            "new_decision_id": new_decision_id,
            "created_at": now,
        })

        if not records:
            raise ValueError(f"Decision or Meeting not found: {decision_id}, {meeting_id}")

        r = records[0]
        return KGSuggestion(
            id=r["id"],
            content=r["content"],
            author_id=r["author_id"],
            status=r["status"],
            decision_id=r["decision_id"],
            created_decision_id=r["created_decision_id"],
            meeting_id=r["meeting_id"],
            created_at=_convert_neo4j_datetime(r["created_at"]),
        )

    async def create_decision_from_suggestion(
        self, suggestion_id: str, original_decision_id: str, content: str, meeting_id: str
    ) -> "KGDecision":
        """Suggestion에서 새 Decision 생성 (레거시 호환용)

        NOTE: 새로운 설계에서는 create_suggestion이 즉시 draft Decision을 생성합니다.
        이 메서드는 기존 API 호환성을 위해 유지됩니다.

        워크플로우:
        1. 새 Decision 노드 생성 (status: 'draft')
        2. 새 Decision -[:SUPERSEDES]-> 원본 Decision
        3. Suggestion → CREATES → 새 Decision
        4. Suggestion status를 'accepted'로 변경
        """
        from app.models.kg import KGDecision

        now = datetime.now(timezone.utc).isoformat()
        new_decision_id = f"decision-{uuid4()}"

        query = """
        MATCH (s:Suggestion {id: $suggestion_id})
        MATCH (d:Decision {id: $original_decision_id})
        MATCH (d)<-[:HAS_DECISION]-(a:Agenda)
        MATCH (m:Meeting {id: $meeting_id})

        // 새 Decision 생성
        CREATE (nd:Decision {
            id: $new_decision_id,
            content: $content,
            context: coalesce(d.context, ''),
            status: 'draft',
            meeting_id: $meeting_id,
            created_at: datetime($created_at)
        })
        CREATE (a)-[:HAS_DECISION]->(nd)
        CREATE (m)-[:DECIDED_IN]->(nd)
        CREATE (nd)-[:SUPERSEDES]->(d)
        CREATE (s)-[:CREATES]->(nd)

        // Suggestion 상태 업데이트
        SET s.status = 'accepted'

        RETURN nd.id as id, nd.content as content, nd.context as context,
               nd.status as status, nd.meeting_id as meeting_id,
               nd.created_at as created_at
        """
        records = await self._execute_write(query, {
            "suggestion_id": suggestion_id,
            "original_decision_id": original_decision_id,
            "content": content,
            "meeting_id": meeting_id,
            "new_decision_id": new_decision_id,
            "created_at": now,
        })

        if not records:
            raise ValueError(f"Suggestion or Decision not found")

        r = records[0]
        return KGDecision(
            id=r["id"],
            content=r["content"],
            context=r["context"],
            status=r["status"],
            meeting_id=r["meeting_id"],
            created_at=_convert_neo4j_datetime(r["created_at"]),
        )

    async def update_suggestion_status(self, suggestion_id: str, status: str) -> bool:
        """Suggestion 상태 업데이트"""
        query = """
        MATCH (s:Suggestion {id: $suggestion_id})
        SET s.status = $status
        RETURN s.id as id
        """
        records = await self._execute_write(query, {
            "suggestion_id": suggestion_id,
            "status": status,
        })
        return len(records) > 0

    # =========================================================================
    # Comment - 댓글
    # =========================================================================

    async def create_comment(
        self, decision_id: str, user_id: str, content: str, pending_agent_reply: bool = False
    ) -> "KGComment":
        """Comment 생성"""
        from app.models.kg import KGComment

        now = datetime.now(timezone.utc).isoformat()
        comment_id = f"comment-{uuid4()}"

        query = """
        MATCH (d:Decision {id: $decision_id})
        MATCH (u:User {id: $user_id})

        CREATE (c:Comment {
            id: $comment_id,
            content: $content,
            pending_agent_reply: $pending_agent_reply,
            created_at: datetime($created_at)
        })
        CREATE (u)-[:COMMENTS]->(c)
        CREATE (c)-[:ON]->(d)

        RETURN c.id as id, $content as content, $user_id as author_id,
               $decision_id as decision_id, c.pending_agent_reply as pending_agent_reply,
               c.created_at as created_at
        """
        records = await self._execute_write(query, {
            "decision_id": decision_id,
            "user_id": user_id,
            "content": content,
            "comment_id": comment_id,
            "pending_agent_reply": pending_agent_reply,
            "created_at": now,
        })

        if not records:
            raise ValueError(f"Decision not found: {decision_id}")

        r = records[0]
        return KGComment(
            id=r["id"],
            content=r["content"],
            author_id=r["author_id"],
            decision_id=r["decision_id"],
            parent_id=None,
            pending_agent_reply=r["pending_agent_reply"] or False,
            created_at=_convert_neo4j_datetime(r["created_at"]),
        )

    async def create_reply(
        self, comment_id: str, user_id: str, content: str, pending_agent_reply: bool = False, is_error_response: bool = False
    ) -> "KGComment":
        """대댓글 생성"""
        from app.models.kg import KGComment

        now = datetime.now(timezone.utc).isoformat()
        reply_id = f"comment-{uuid4()}"

        query = """
        MATCH (parent:Comment {id: $comment_id})
        MATCH (u:User {id: $user_id})
        MATCH (parent)-[:ON]->(d:Decision)

        CREATE (r:Comment {
            id: $reply_id,
            content: $content,
            pending_agent_reply: $pending_agent_reply,
            is_error_response: $is_error_response,
            created_at: datetime($created_at)
        })
        CREATE (u)-[:COMMENTS]->(r)
        CREATE (r)-[:REPLY_TO]->(parent)
        CREATE (r)-[:ON]->(d)

        RETURN r.id as id, $content as content, $user_id as author_id,
               d.id as decision_id, $comment_id as parent_id,
               r.pending_agent_reply as pending_agent_reply,
               r.is_error_response as is_error_response, r.created_at as created_at
        """
        records = await self._execute_write(query, {
            "comment_id": comment_id,
            "user_id": user_id,
            "content": content,
            "reply_id": reply_id,
            "pending_agent_reply": pending_agent_reply,
            "is_error_response": is_error_response,
            "created_at": now,
        })

        if not records:
            raise ValueError(f"Comment not found: {comment_id}")

        r = records[0]
        return KGComment(
            id=r["id"],
            content=r["content"],
            author_id=r["author_id"],
            decision_id=r["decision_id"],
            parent_id=r["parent_id"],
            pending_agent_reply=r["pending_agent_reply"] or False,
            is_error_response=r.get("is_error_response") or False,
            created_at=_convert_neo4j_datetime(r["created_at"]),
        )

    async def delete_comment(self, comment_id: str, user_id: str) -> dict | None:
        """Comment 삭제 (작성자 확인 + CASCADE)

        Returns:
            dict | None: 삭제 성공 시 {decision_id, meeting_id}, 실패 시 None
        """
        # 삭제 전에 정보 조회
        query = """
        MATCH (u:User {id: $user_id})-[:COMMENTS]->(c:Comment {id: $comment_id})
        MATCH (c)-[:ON]->(d:Decision)

        // 대댓글도 함께 삭제
        OPTIONAL MATCH (reply:Comment)-[:REPLY_TO]->(c)
        DETACH DELETE reply

        DETACH DELETE c
        RETURN d.id as decision_id, d.meeting_id as meeting_id
        """
        records = await self._execute_write(query, {
            "comment_id": comment_id,
            "user_id": user_id,
        })
        if not records:
            return None
        r = records[0]
        return {
            "decision_id": r.get("decision_id"),
            "meeting_id": r.get("meeting_id"),
        }

    # =========================================================================
    # Decision CRUD 확장
    # =========================================================================

    async def update_decision(
        self, decision_id: str, user_id: str, data: dict
    ) -> KGDecision:
        """Decision 수정"""
        set_clauses = []
        params = {"decision_id": decision_id, "user_id": user_id}
        for key, value in data.items():
            if key in ("content", "context"):
                set_clauses.append(f"d.{key} = ${key}")
                params[key] = value

        if not set_clauses:
            decision = await self.get_decision(decision_id)
            if not decision:
                raise ValueError(f"Decision not found: {decision_id}")
            return decision

        query = f"""
        MATCH (d:Decision {{id: $decision_id}})
        SET {', '.join(set_clauses)}
        RETURN d.id as id
        """
        records = await self._execute_write(query, params)

        if not records:
            raise ValueError(f"Decision not found: {decision_id}")

        return await self.get_decision(decision_id)  # type: ignore

    async def delete_decision(self, decision_id: str, user_id: str) -> bool:
        """Decision 삭제 (전체 CASCADE)"""
        query = """
        MATCH (d:Decision {id: $decision_id})

        // 관련 Comment 삭제
        OPTIONAL MATCH (c:Comment)-[:ON]->(d)
        OPTIONAL MATCH (reply:Comment)-[:REPLY_TO]->(c)
        DETACH DELETE reply
        DETACH DELETE c

        // 관련 Suggestion 삭제
        OPTIONAL MATCH (s:Suggestion)-[:CREATES]->(d)
        DETACH DELETE s

        // 관련 ActionItem 삭제
        OPTIONAL MATCH (d)-[:TRIGGERS]->(ai:ActionItem)
        DETACH DELETE ai

        DETACH DELETE d
        RETURN true as deleted
        """
        records = await self._execute_write(query, {"decision_id": decision_id})
        return len(records) > 0

    # =========================================================================
    # Agenda CRUD
    # =========================================================================

    async def update_agenda(
        self, agenda_id: str, user_id: str, data: dict
    ) -> KGAgenda:
        """Agenda 수정"""
        set_clauses = []
        params = {"agenda_id": agenda_id}
        for key, value in data.items():
            if key in ("topic", "description"):
                set_clauses.append(f"a.{key} = ${key}")
                params[key] = value

        if not set_clauses:
            raise ValueError(f"Agenda not found: {agenda_id}")

        query = f"""
        MATCH (a:Agenda {{id: $agenda_id}})
        OPTIONAL MATCH (m:Meeting)-[:CONTAINS]->(a)
        SET {', '.join(set_clauses)}
        RETURN a.id as id, a.topic as topic, a.description as description,
               a.order as order, m.id as meeting_id
        """
        records = await self._execute_write(query, params)

        if not records:
            raise ValueError(f"Agenda not found: {agenda_id}")

        r = records[0]
        return KGAgenda(
            id=r["id"],
            topic=r["topic"] or "",
            description=r["description"],
            order=r["order"] or 0,
            meeting_id=r["meeting_id"],
        )

    async def delete_agenda(self, agenda_id: str, user_id: str) -> dict | None:
        """Agenda 삭제 (전체 CASCADE)

        Returns:
            삭제된 경우: {"meeting_id": str}
            실패한 경우: None
        """
        query = """
        MATCH (a:Agenda {id: $agenda_id})

        // meeting_id 먼저 저장
        WITH a, a.meeting_id as meeting_id

        // 관련 Decision과 하위 엔티티 삭제
        OPTIONAL MATCH (a)-[:HAS_DECISION]->(d:Decision)
        OPTIONAL MATCH (c:Comment)-[:ON]->(d)
        OPTIONAL MATCH (reply:Comment)-[:REPLY_TO]->(c)
        OPTIONAL MATCH (s:Suggestion)-[:CREATES]->(d)
        OPTIONAL MATCH (d)-[:TRIGGERS]->(ai:ActionItem)

        DETACH DELETE reply
        DETACH DELETE c
        DETACH DELETE s
        DETACH DELETE ai
        DETACH DELETE d
        DETACH DELETE a

        RETURN meeting_id
        """
        records = await self._execute_write(query, {"agenda_id": agenda_id})
        if records:
            r = records[0]
            return {"meeting_id": r.get("meeting_id")}
        return None

    # =========================================================================
    # ActionItem CRUD 확장
    # =========================================================================

    async def get_action_items(
        self, user_id: str | None = None, status: str | None = None
    ) -> list["KGActionItem"]:
        """ActionItem 목록 조회 (필터링)"""
        from app.models.kg import KGActionItem

        where_clauses = []
        params: dict[str, Any] = {}

        if user_id:
            where_clauses.append("assignee.id = $user_id")
            params["user_id"] = user_id
        if status:
            where_clauses.append("ai.status = $status")
            params["status"] = status

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
        MATCH (ai:ActionItem)
        OPTIONAL MATCH (assignee:User)-[:ASSIGNED_TO]->(ai)
        OPTIONAL MATCH (d:Decision)-[:TRIGGERS]->(ai)
        {where_clause}
        RETURN ai.id as id, ai.title as title, ai.description as description,
               ai.status as status, assignee.id as assignee_id,
               ai.due_date as due_date, d.id as decision_id
        """
        records = await self._execute_read(query, params)

        return [
            KGActionItem(
                id=r["id"],
                title=r["title"] or "",
                description=r["description"],
                status=r["status"] or "pending",
                assignee_id=r["assignee_id"],
                due_date=_convert_neo4j_datetime(r["due_date"]) if r["due_date"] else None,
                decision_id=r["decision_id"],
            )
            for r in records
        ]

    async def update_action_item(
        self, action_item_id: str, user_id: str, data: dict
    ) -> "KGActionItem":
        """ActionItem 수정"""
        from app.models.kg import KGActionItem

        set_clauses = []
        params: dict[str, Any] = {"action_item_id": action_item_id}

        for key, value in data.items():
            if key in ("title", "description", "status"):
                set_clauses.append(f"ai.{key} = ${key}")
                params[key] = value
            elif key == "due_date" and value:
                set_clauses.append("ai.due_date = datetime($due_date)")
                params["due_date"] = value.isoformat() if hasattr(value, 'isoformat') else value

        if not set_clauses:
            raise ValueError(f"ActionItem not found: {action_item_id}")

        query = f"""
        MATCH (ai:ActionItem {{id: $action_item_id}})
        OPTIONAL MATCH (assignee:User)-[:ASSIGNED_TO]->(ai)
        OPTIONAL MATCH (d:Decision)-[:TRIGGERS]->(ai)
        SET {', '.join(set_clauses)}
        RETURN ai.id as id, ai.title as title, ai.description as description,
               ai.status as status, assignee.id as assignee_id,
               ai.due_date as due_date, d.id as decision_id
        """
        records = await self._execute_write(query, params)

        if not records:
            raise ValueError(f"ActionItem not found: {action_item_id}")

        r = records[0]
        return KGActionItem(
            id=r["id"],
            title=r["title"] or "",
            description=r["description"],
            status=r["status"] or "pending",
            assignee_id=r["assignee_id"],
            due_date=_convert_neo4j_datetime(r["due_date"]) if r["due_date"] else None,
            decision_id=r["decision_id"],
        )

    async def delete_action_item(self, action_item_id: str, user_id: str) -> bool:
        """ActionItem 삭제"""
        query = """
        MATCH (ai:ActionItem {id: $action_item_id})
        DETACH DELETE ai
        RETURN true as deleted
        """
        records = await self._execute_write(query, {"action_item_id": action_item_id})
        return len(records) > 0

    # =========================================================================
    # Minutes View
    # =========================================================================

    async def get_minutes_view(self, meeting_id: str) -> dict:
        """Minutes 전체 View 조회 (중첩 구조)"""
        # 1. Meeting + Summary 조회
        meeting_query = """
        MATCH (m:Meeting {id: $meeting_id})
        RETURN m.id as meeting_id, m.summary as summary
        """
        meeting_records = await self._execute_read(meeting_query, {"meeting_id": meeting_id})
        if not meeting_records:
            return {}

        meeting = meeting_records[0]

        # 2. Agendas 조회
        agenda_query = """
        MATCH (m:Meeting {id: $meeting_id})-[:CONTAINS]->(a:Agenda)
        RETURN a.id as id, a.topic as topic, a.description as description, a.order as order
        ORDER BY a.order
        """
        agenda_records = await self._execute_read(agenda_query, {"meeting_id": meeting_id})

        agendas = []
        for a in agenda_records:
            # 3. Decisions per Agenda (with approvers/rejectors)
            # active Decision만 조회 (superseded, outdated, rejected 제외)
            decision_query = """
            MATCH (a:Agenda {id: $agenda_id})-[:HAS_DECISION]->(d:Decision)
            WHERE NOT (d.status IN ['superseded', 'outdated', 'rejected'])
            OPTIONAL MATCH (approver:User)-[:APPROVED_BY]->(d)
            OPTIONAL MATCH (rejector:User)-[:REJECTED_BY]->(d)
            // 이전 GT 조회 (OUTDATES 관계 - latest → outdated)
            OPTIONAL MATCH (d)-[:OUTDATES]->(prev:Decision)
            WHERE prev.status = 'outdated'
            RETURN d.id as id, d.content as content, d.context as context,
                   d.status as status, d.meeting_id as meeting_id,
                   d.created_at as created_at, d.updated_at as updated_at,
                   [x IN collect(DISTINCT approver.id) WHERE x IS NOT NULL] as approvers,
                   [x IN collect(DISTINCT rejector.id) WHERE x IS NOT NULL] as rejectors,
                   prev.id as supersedes_id, prev.content as supersedes_content,
                   prev.meeting_id as supersedes_meeting_id
            """
            decision_records = await self._execute_read(decision_query, {"agenda_id": a["id"]})

            decisions = []
            for d in decision_records:
                # 4. Suggestions per Decision ([:ON] 관계로 조회 - AI 분석 전 Suggestion도 포함)
                suggestion_query = """
                MATCH (s:Suggestion)-[:ON]->(d:Decision {id: $decision_id})
                MATCH (u:User)-[:SUGGESTS]->(s)
                OPTIONAL MATCH (s)-[:CREATES]->(cd:Decision)
                RETURN s.id as id, s.content as content,
                       u.id as author_id, u.name as author_name, u.email as author_email,
                       s.status as status,
                       cd.id as cd_id, cd.content as cd_content, cd.status as cd_status,
                       s.created_at as created_at
                """
                suggestion_records = await self._execute_read(suggestion_query, {"decision_id": d["id"]})
                suggestions = [
                    {
                        "id": s["id"],
                        "content": s["content"],
                        "author": {
                            "id": s["author_id"],
                            "name": s["author_name"] or "",
                            "email": s["author_email"] or "",
                        },
                        "created_decision": {
                            "id": s["cd_id"],
                            "content": s["cd_content"] or "",
                            "status": s["cd_status"] or "draft",
                        } if s["cd_id"] else None,
                        "created_at": _convert_neo4j_datetime(s["created_at"]).isoformat(),
                    }
                    for s in suggestion_records
                ]

                # 5. Comments per Decision (모든 depth를 단일 쿼리로 조회)
                comment_query = """
                MATCH (u:User)-[:COMMENTS]->(c:Comment)-[:ON]->(d:Decision {id: $decision_id})
                OPTIONAL MATCH (c)-[:REPLY_TO]->(parent:Comment)
                RETURN c.id as id, c.content as content,
                       u.id as author_id, u.name as author_name, u.email as author_email,
                       c.pending_agent_reply as pending_agent_reply,
                       c.is_error_response as is_error_response,
                       c.created_at as created_at,
                       parent.id as parent_id
                ORDER BY c.created_at
                """
                comment_records = await self._execute_read(comment_query, {"decision_id": d["id"]})

                # 6. History: SUPERSEDES 체인을 따라 superseded된 Decision들 조회
                # 같은 Meeting 스코프 내 + superseded 상태만 (Suggestion 히스토리)
                # OUTDATES 관계(GT 변화)는 제외
                history_query = """
                MATCH (current:Decision {id: $decision_id})-[:SUPERSEDES*]->(prev:Decision)
                WHERE prev.meeting_id = $meeting_id AND prev.status = 'superseded'
                RETURN prev.id as id, prev.content as content, prev.status as status,
                       prev.created_at as created_at
                ORDER BY prev.created_at DESC
                """
                history_records = await self._execute_read(
                    history_query, {"decision_id": d["id"], "meeting_id": meeting_id}
                )
                history = [
                    {
                        "id": h["id"],
                        "content": h["content"] or "",
                        "status": h["status"] or "superseded",
                        "created_at": _convert_neo4j_datetime(h["created_at"]).isoformat(),
                    }
                    for h in history_records
                ]

                # Flat list 생성
                flat_comments = [
                    {
                        "id": c["id"],
                        "content": c["content"],
                        "author": {
                            "id": c["author_id"],
                            "name": c["author_name"] or "",
                            "email": c["author_email"] or "",
                        },
                        "pending_agent_reply": c["pending_agent_reply"] or False,
                        "is_error_response": c.get("is_error_response") or False,
                        "created_at": _convert_neo4j_datetime(c["created_at"]).isoformat(),
                        "parent_id": c["parent_id"],
                    }
                    for c in comment_records
                ]

                # Tree 구조로 변환 (무제한 depth 지원)
                comments = _build_comment_tree(flat_comments)

                decisions.append({
                    "id": d["id"],
                    "content": d["content"] or "",
                    "context": d["context"],
                    "status": d["status"] or "draft",
                    "meeting_id": d["meeting_id"],
                    "approvers": d["approvers"] or [],
                    "rejectors": d["rejectors"] or [],
                    "created_at": _convert_neo4j_datetime(d["created_at"]).isoformat(),
                    "updated_at": _convert_neo4j_datetime(d["updated_at"]).isoformat() if d.get("updated_at") else None,
                    "suggestions": suggestions,
                    "comments": comments,
                    # 이전 버전 정보 (GT 표시용)
                    "supersedes": {
                        "id": d["supersedes_id"],
                        "content": d["supersedes_content"] or "",
                        "meeting_id": d["supersedes_meeting_id"],
                    } if d.get("supersedes_id") else None,
                    # 히스토리: 같은 Meeting 스코프 내 superseded된 모든 이전 버전
                    "history": history,
                })

            agendas.append({
                "id": a["id"],
                "topic": a["topic"] or "",
                "description": a["description"],
                "order": a["order"] or 0,
                "decisions": decisions,
            })

        # 7. ActionItems 조회
        action_item_query = """
        MATCH (m:Meeting {id: $meeting_id})-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)-[:TRIGGERS]->(ai:ActionItem)
        OPTIONAL MATCH (assignee:User)-[:ASSIGNED_TO]->(ai)
        RETURN ai.id as id, ai.title as title, ai.status as status,
               assignee.id as assignee_id, ai.due_date as due_date
        """
        action_item_records = await self._execute_read(action_item_query, {"meeting_id": meeting_id})
        action_items = [
            {
                "id": ai["id"],
                "title": ai["title"] or "",
                "status": ai["status"] or "pending",
                "assignee_id": ai["assignee_id"],
                "due_date": _convert_neo4j_datetime(ai["due_date"]).isoformat() if ai["due_date"] else None,
            }
            for ai in action_item_records
        ]

        return {
            "meeting_id": meeting["meeting_id"],
            "summary": meeting["summary"] or "",
            "agendas": agendas,
            "action_items": action_items,
        }

    async def get_or_create_system_agent(self) -> str:
        """MIT Agent 시스템 사용자 조회/생성

        Returns:
            str: mit-agent 사용자 ID
        """
        agent_id = "mit-agent"
        agent_name = "MIT Agent"

        query = """
        MERGE (u:User {id: $agent_id})
        ON CREATE SET u.name = $agent_name, u.created_at = datetime()
        RETURN u.id as id
        """
        records = await self._execute_write(
            query, {"agent_id": agent_id, "agent_name": agent_name}
        )
        return records[0]["id"] if records else agent_id

    async def update_comment_pending_agent_reply(
        self, comment_id: str, pending: bool
    ) -> bool:
        """Comment의 pending_agent_reply 상태 업데이트

        Args:
            comment_id: Comment ID
            pending: pending_agent_reply 상태

        Returns:
            bool: 업데이트 성공 여부
        """
        query = """
        MATCH (c:Comment {id: $comment_id})
        SET c.pending_agent_reply = $pending
        RETURN c.id as id
        """
        records = await self._execute_write(
            query, {"comment_id": comment_id, "pending": pending}
        )
        return len(records) > 0

    async def get_comment_pending_status(self, comment_id: str) -> bool | None:
        """Comment의 pending_agent_reply 상태 조회

        Args:
            comment_id: Comment ID

        Returns:
            bool | None: pending_agent_reply 상태 (Comment가 없으면 None)
        """
        query = """
        MATCH (c:Comment {id: $comment_id})
        RETURN c.pending_agent_reply as pending
        """
        records = await self._execute_read(query, {"comment_id": comment_id})
        if not records:
            return None
        return records[0].get("pending", False)

    async def get_decision_thread_history(
        self, decision_id: str
    ) -> list[dict]:
        """Decision에 달린 모든 Comment/Reply 이력 조회

        AI가 이전 논의를 참고할 수 있도록 시간순 정렬된 대화 이력 반환

        Args:
            decision_id: Decision ID

        Returns:
            list[dict]: 대화 이력 [{role, content, author_name, created_at}, ...]
        """
        from app.constants.agents import AI_AGENTS

        query = """
        MATCH (u:User)-[:COMMENTS]->(c:Comment)-[:ON]->(d:Decision {id: $decision_id})
        RETURN c.id as id, c.content as content,
               u.id as author_id, u.name as author_name,
               c.created_at as created_at
        ORDER BY c.created_at
        """
        records = await self._execute_read(query, {"decision_id": decision_id})

        # AI agent ID 목록
        agent_ids = {agent.id for agent in AI_AGENTS}

        history = []
        for r in records:
            is_ai = r["author_id"] in agent_ids
            history.append({
                "role": "assistant" if is_ai else "user",
                "content": r["content"] or "",
                "author_name": r["author_name"] or "",
                "created_at": _convert_neo4j_datetime(r["created_at"]).isoformat(),
            })

        return history

    async def get_meeting_context(self, meeting_id: str) -> dict | None:
        """Meeting 컨텍스트 조회 (AI 응답 생성용)

        Args:
            meeting_id: Meeting ID

        Returns:
            {
                "meeting_title": str,
                "meeting_date": str,
                "agenda_topics": list[str],  # 같은 회의의 Agenda 주제들
                "other_decisions": list[dict],  # 같은 회의의 다른 Decision 요약
            }
        """
        query = """
        MATCH (m:Meeting {id: $meeting_id})
        OPTIONAL MATCH (m)-[:CONTAINS]->(a:Agenda)
        OPTIONAL MATCH (a)-[:HAS_DECISION]->(d:Decision)
        WHERE d.status IN ['draft', 'latest']
        RETURN m.title as title, m.started_at as date,
               collect(DISTINCT a.topic) as agendas,
               collect(DISTINCT {id: d.id, content: d.content}) as decisions
        """
        records = await self._execute_read(query, {"meeting_id": meeting_id})

        if not records:
            return None

        r = records[0]

        # Filter out null values from collections
        agenda_topics = [topic for topic in r.get("agendas", []) if topic]
        decisions = [
            {"id": d["id"], "content": d["content"]}
            for d in r.get("decisions", [])
            if d.get("id") and d.get("content")
        ]

        return {
            "meeting_title": r.get("title", ""),
            "meeting_date": _convert_neo4j_datetime(r.get("date")).isoformat() if r.get("date") else "",
            "agenda_topics": agenda_topics,
            "other_decisions": decisions,
        }
