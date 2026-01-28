"""Neo4j KG Repository

Raw Cypher 기반 Knowledge Graph 저장소.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from neo4j import AsyncDriver
from neo4j.time import DateTime as Neo4jDateTime

from app.models.kg import (
    KGAgenda,
    KGDecision,
    KGMeeting,
    KGMinutes,
    KGMinutesActionItem,
    KGMinutesDecision,
)


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
        """결정 머지 (status -> merged)

        Returns:
            bool: 머지 성공 여부 (decision이 존재하면 True)
        """
        query = """
        MATCH (d:Decision {id: $decision_id})
        SET d.status = 'merged', d.merged_at = datetime()
        RETURN d.id as decision_id
        """
        records = await self._execute_write(query, {"decision_id": decision_id})
        return len(records) > 0

    async def approve_and_merge_if_complete(
        self, decision_id: str, user_id: str
    ) -> dict:
        """결정 승인 + 전원 승인 시 자동 머지 (원자적 트랜잭션)

        단일 Cypher 쿼리로 승인 관계 생성, 전원 승인 확인, 머지를 처리.
        Race condition 없이 원자적으로 처리됨.

        Returns:
            {
                "approved": bool,       # 승인 성공 여부
                "merged": bool,         # 머지 여부
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
        WITH d, collect(DISTINCT participant.id) as participants

        OPTIONAL MATCH (approver:User)-[:APPROVED_BY]->(d)
        WITH d, participants, collect(DISTINCT approver.id) as approvers

        // 3. 전원 승인 시 자동 머지
        WITH d, participants, approvers,
             size(participants) as p_count,
             size(approvers) as a_count
        SET d.status = CASE
            WHEN p_count = a_count THEN 'merged'
            ELSE d.status
        END,
        d.merged_at = CASE
            WHEN p_count = a_count THEN datetime()
            ELSE d.merged_at
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
            status=d.get("status", "pending"),
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
