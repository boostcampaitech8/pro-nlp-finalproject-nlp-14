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
        WITH m, a, agenda_data
        WHERE agenda_data.decision IS NOT NULL
        CREATE (d:Decision {
            id: 'decision-' + randomUUID(),
            content: agenda_data.decision.content,
            context: coalesce(agenda_data.decision.context, ''),
            status: 'draft',
            created_at: datetime($created_at)
        })
        CREATE (a)-[:HAS_DECISION]->(d)

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

        Returns:
            bool: 승격 성공 여부 (decision이 존재하면 True)
        """
        query = """
        MATCH (d:Decision {id: $decision_id})

        // 1. 동일 Agenda의 기존 latest -> outdated
        OPTIONAL MATCH (d)<-[:HAS_DECISION]-(a:Agenda)-[:HAS_DECISION]->(old:Decision)
        WHERE old.status = 'latest' AND old.id <> $decision_id
        SET old.status = 'outdated'

        // 2. 현재 Decision -> latest
        WITH d
        SET d.status = 'latest', d.approved_at = datetime()
        RETURN d.id as decision_id
        """
        records = await self._execute_write(query, {"decision_id": decision_id})
        return len(records) > 0

    async def approve_and_merge_if_complete(
        self, decision_id: str, user_id: str
    ) -> dict:
        """결정 승인 + 전원 승인 시 자동 승격 (원자적 트랜잭션)

        단일 Cypher 쿼리로 승인 관계 생성, 전원 승인 확인, latest 승격을 처리.
        Race condition 없이 원자적으로 처리됨.
        전원 승인 시 동일 Agenda의 기존 latest Decision은 outdated로 변경됨.

        Returns:
            {
                "approved": bool,       # 승인 성공 여부
                "merged": bool,         # latest 승격 여부
                "status": str,          # 최종 상태
                "approvers_count": int,
                "participants_count": int,
            }
        """
        query = """
        MATCH (d:Decision {id: $decision_id})
        MATCH (u:User {id: $user_id})

        // 1. 승인 관계 생성 (MERGE로 중복 방지)
        MERGE (u)-[:APPROVED_BY]->(d)

        // 2. 참여자 수와 승인자 수 계산
        WITH d
        MATCH (d)<-[:HAS_DECISION]-(a:Agenda)<-[:CONTAINS]-(m:Meeting)
        MATCH (participant:User)-[:PARTICIPATED_IN]->(m)
        WITH d, a, collect(DISTINCT participant.id) as participants

        OPTIONAL MATCH (approver:User)-[:APPROVED_BY]->(d)
        WITH d, a, participants, collect(DISTINCT approver.id) as approvers

        // 3. 전원 승인 시: 기존 latest -> outdated
        WITH d, a, participants, approvers,
             size(participants) as p_count,
             size(approvers) as a_count
        OPTIONAL MATCH (a)-[:HAS_DECISION]->(old:Decision)
        WHERE old.status = 'latest' AND old.id <> d.id AND p_count = a_count
        SET old.status = 'outdated'

        // 4. 전원 승인 시: 현재 Decision -> latest
        WITH d, participants, approvers, p_count, a_count
        SET d.status = CASE
            WHEN p_count = a_count THEN 'latest'
            ELSE d.status
        END,
        d.approved_at = CASE
            WHEN p_count = a_count THEN datetime()
            ELSE d.approved_at
        END

        RETURN d.id as decision_id,
               d.status as status,
               p_count as participants_count,
               a_count as approvers_count,
               p_count = a_count as merged
        """
        records = await self._execute_write(
            query, {"decision_id": decision_id, "user_id": user_id}
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
        RETURN d, a, m,
               collect(DISTINCT approver.id) as approvers,
               collect(DISTINCT rejector.id) as rejectors
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
            created_at=_convert_neo4j_datetime(d.get("created_at")),
            agenda_id=a.get("id"),
            agenda_topic=a.get("topic"),
            meeting_title=m.get("title"),
            approvers=[aid for aid in record["approvers"] if aid],
            rejectors=[rid for rid in record["rejectors"] if rid],
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
        self, decision_id: str, user_id: str, content: str
    ) -> "KGSuggestion":
        """Suggestion + 새 Decision 생성 (원자적)"""
        from app.models.kg import KGSuggestion

        now = datetime.now(timezone.utc).isoformat()
        suggestion_id = f"suggestion-{uuid4()}"
        new_decision_id = f"decision-{uuid4()}"

        query = """
        MATCH (d:Decision {id: $decision_id})
        MATCH (u:User {id: $user_id})
        MATCH (d)<-[:HAS_DECISION]-(a:Agenda)

        // 새 Decision 생성 (draft)
        CREATE (nd:Decision {
            id: $new_decision_id,
            content: $content,
            context: '',
            status: 'draft',
            created_at: datetime($created_at)
        })
        CREATE (a)-[:HAS_DECISION]->(nd)
        CREATE (d)-[:SUPERSEDED_BY]->(nd)

        // Suggestion 생성
        CREATE (s:Suggestion {
            id: $suggestion_id,
            content: $content,
            created_at: datetime($created_at)
        })
        CREATE (u)-[:SUGGESTS]->(s)
        CREATE (s)-[:CREATES]->(nd)

        RETURN s.id as id, $content as content, $user_id as author_id,
               nd.id as created_decision_id, s.created_at as created_at
        """
        records = await self._execute_write(query, {
            "decision_id": decision_id,
            "user_id": user_id,
            "content": content,
            "suggestion_id": suggestion_id,
            "new_decision_id": new_decision_id,
            "created_at": now,
        })

        if not records:
            raise ValueError(f"Decision not found: {decision_id}")

        r = records[0]
        return KGSuggestion(
            id=r["id"],
            content=r["content"],
            author_id=r["author_id"],
            created_decision_id=r["created_decision_id"],
            created_at=_convert_neo4j_datetime(r["created_at"]),
        )

    # =========================================================================
    # Comment - 댓글
    # =========================================================================

    async def create_comment(
        self, decision_id: str, user_id: str, content: str
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
            created_at: datetime($created_at)
        })
        CREATE (u)-[:COMMENTS]->(c)
        CREATE (c)-[:ON]->(d)

        RETURN c.id as id, $content as content, $user_id as author_id,
               $decision_id as decision_id, c.created_at as created_at
        """
        records = await self._execute_write(query, {
            "decision_id": decision_id,
            "user_id": user_id,
            "content": content,
            "comment_id": comment_id,
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
            created_at=_convert_neo4j_datetime(r["created_at"]),
        )

    async def create_reply(
        self, comment_id: str, user_id: str, content: str
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
            created_at: datetime($created_at)
        })
        CREATE (u)-[:COMMENTS]->(r)
        CREATE (r)-[:REPLY_TO]->(parent)
        CREATE (r)-[:ON]->(d)

        RETURN r.id as id, $content as content, $user_id as author_id,
               d.id as decision_id, $comment_id as parent_id, r.created_at as created_at
        """
        records = await self._execute_write(query, {
            "comment_id": comment_id,
            "user_id": user_id,
            "content": content,
            "reply_id": reply_id,
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
            created_at=_convert_neo4j_datetime(r["created_at"]),
        )

    async def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """Comment 삭제 (작성자 확인 + CASCADE)"""
        query = """
        MATCH (u:User {id: $user_id})-[:COMMENTS]->(c:Comment {id: $comment_id})

        // 대댓글도 함께 삭제
        OPTIONAL MATCH (reply:Comment)-[:REPLY_TO]->(c)
        DETACH DELETE reply

        DETACH DELETE c
        RETURN true as deleted
        """
        records = await self._execute_write(query, {
            "comment_id": comment_id,
            "user_id": user_id,
        })
        return len(records) > 0

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

    async def delete_agenda(self, agenda_id: str, user_id: str) -> bool:
        """Agenda 삭제 (전체 CASCADE)"""
        query = """
        MATCH (a:Agenda {id: $agenda_id})

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

        RETURN true as deleted
        """
        records = await self._execute_write(query, {"agenda_id": agenda_id})
        return len(records) > 0

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
            # 3. Decisions per Agenda
            decision_query = """
            MATCH (a:Agenda {id: $agenda_id})-[:HAS_DECISION]->(d:Decision)
            RETURN d.id as id, d.content as content, d.context as context,
                   d.status as status, d.created_at as created_at
            """
            decision_records = await self._execute_read(decision_query, {"agenda_id": a["id"]})

            decisions = []
            for d in decision_records:
                # 4. Suggestions per Decision
                suggestion_query = """
                MATCH (s:Suggestion)-[:CREATES]->(nd:Decision)
                MATCH (d:Decision {id: $decision_id})-[:SUPERSEDED_BY]->(nd)
                MATCH (u:User)-[:SUGGESTS]->(s)
                RETURN s.id as id, s.content as content, u.id as author_id,
                       nd.id as created_decision_id, s.created_at as created_at
                """
                suggestion_records = await self._execute_read(suggestion_query, {"decision_id": d["id"]})
                suggestions = [
                    {
                        "id": s["id"],
                        "content": s["content"],
                        "author_id": s["author_id"],
                        "created_decision_id": s["created_decision_id"],
                        "created_at": _convert_neo4j_datetime(s["created_at"]).isoformat(),
                    }
                    for s in suggestion_records
                ]

                # 5. Comments per Decision (top-level only)
                comment_query = """
                MATCH (u:User)-[:COMMENTS]->(c:Comment)-[:ON]->(d:Decision {id: $decision_id})
                WHERE NOT (c)-[:REPLY_TO]->()
                RETURN c.id as id, c.content as content, u.id as author_id, c.created_at as created_at
                """
                comment_records = await self._execute_read(comment_query, {"decision_id": d["id"]})

                comments = []
                for c in comment_records:
                    # 6. Replies per Comment
                    reply_query = """
                    MATCH (u:User)-[:COMMENTS]->(r:Comment)-[:REPLY_TO]->(c:Comment {id: $comment_id})
                    RETURN r.id as id, r.content as content, u.id as author_id, r.created_at as created_at
                    """
                    reply_records = await self._execute_read(reply_query, {"comment_id": c["id"]})
                    replies = [
                        {
                            "id": r["id"],
                            "content": r["content"],
                            "author_id": r["author_id"],
                            "created_at": _convert_neo4j_datetime(r["created_at"]).isoformat(),
                        }
                        for r in reply_records
                    ]
                    comments.append({
                        "id": c["id"],
                        "content": c["content"],
                        "author_id": c["author_id"],
                        "replies": replies,
                        "created_at": _convert_neo4j_datetime(c["created_at"]).isoformat(),
                    })

                decisions.append({
                    "id": d["id"],
                    "content": d["content"] or "",
                    "context": d["context"],
                    "status": d["status"] or "draft",
                    "created_at": _convert_neo4j_datetime(d["created_at"]).isoformat(),
                    "suggestions": suggestions,
                    "comments": comments,
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
