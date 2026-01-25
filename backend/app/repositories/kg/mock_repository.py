"""Mock KG Repository

테스트용 Mock Knowledge Graph 저장소.
"""

import copy
from datetime import datetime, timezone
from uuid import uuid4

from app.models.kg import (
    KGAgenda,
    KGDecision,
    KGMeeting,
    KGMinutes,
    KGMinutesActionItem,
    KGMinutesDecision,
)

# =============================================================================
# Mock 데이터 저장소
# =============================================================================

MOCK_DATA = {
    "teams": {
        "team-1": {
            "id": "team-1",
            "name": "개발팀",
            "description": "백엔드/프론트엔드 개발",
        },
        "team-2": {
            "id": "team-2",
            "name": "기획팀",
            "description": "제품 기획 및 UX 설계",
        },
    },
    "users": {
        "user-1": {
            "id": "user-1",
            "name": "김민준",
            "email": "minjun@example.com",
        },
        "user-2": {
            "id": "user-2",
            "name": "이서연",
            "email": "seoyeon@example.com",
        },
        "user-3": {
            "id": "user-3",
            "name": "박지훈",
            "email": "jihun@example.com",
        },
    },
    "meetings": {
        "meeting-1": {
            "id": "meeting-1",
            "title": "스프린트 계획 회의",
            "status": "completed",
            "team_id": "team-1",
            "participant_ids": ["user-1", "user-2"],
            "created_at": "2026-01-20T09:00:00+00:00",
        },
        "meeting-2": {
            "id": "meeting-2",
            "title": "API 설계 리뷰",
            "status": "completed",
            "team_id": "team-1",
            "participant_ids": ["user-1", "user-2", "user-3"],
            "created_at": "2026-01-22T13:00:00+00:00",
        },
    },
    "agendas": {
        "agenda-1": {
            "id": "agenda-1",
            "topic": "API 설계 검토",
            "description": "RESTful API 엔드포인트 설계 방향 논의",
            "meeting_id": "meeting-1",
            "order": 1,
        },
        "agenda-2": {
            "id": "agenda-2",
            "topic": "프로젝트 일정",
            "description": "마일스톤 및 데드라인 확정",
            "meeting_id": "meeting-1",
            "order": 2,
        },
        "agenda-3": {
            "id": "agenda-3",
            "topic": "인증 방식 결정",
            "description": "JWT vs Session 기반 인증",
            "meeting_id": "meeting-2",
            "order": 1,
        },
    },
    "decisions": {
        "decision-1": {
            "id": "decision-1",
            "content": "RESTful API 설계 원칙 준수",
            "context": "API 일관성 유지 및 클라이언트 개발 편의성을 위해",
            "status": "merged",
            "agenda_id": "agenda-1",
            "created_at": "2026-01-20T10:00:00+00:00",
        },
        "decision-2": {
            "id": "decision-2",
            "content": "1차 마일스톤: 2월 15일",
            "context": "MVP 기능 완성 목표",
            "status": "merged",
            "agenda_id": "agenda-2",
            "created_at": "2026-01-20T10:30:00+00:00",
        },
        "decision-3": {
            "id": "decision-3",
            "content": "JWT 기반 인증 채택",
            "context": "마이크로서비스 확장성과 stateless 특성 고려",
            "status": "pending",
            "agenda_id": "agenda-3",
            "created_at": "2026-01-22T14:00:00+00:00",
        },
    },
    "action_items": {
        "action-1": {
            "id": "action-1",
            "title": "API 문서 작성",
            "description": "OpenAPI 스펙 기반 API 문서화",
            "status": "pending",
            "due_date": "2026-02-01",
            "assignee_id": "user-1",
            "decision_id": "decision-1",
        },
        "action-2": {
            "id": "action-2",
            "title": "JWT 라이브러리 선정",
            "description": "Python JWT 라이브러리 비교 및 선정",
            "status": "in_progress",
            "due_date": "2026-01-28",
            "assignee_id": "user-2",
            "decision_id": "decision-3",
        },
    },
    "minutes": {
        "minutes-1": {
            "id": "minutes-1",
            "meeting_id": "meeting-1",
            "summary": "스프린트 계획 및 API 설계 방향 논의. RESTful 원칙 준수와 1차 마일스톤 일정을 확정함.",
            "created_at": "2026-01-20T11:00:00+00:00",
        },
    },
    # 관계 데이터
    "approvals": [
        ("user-1", "decision-1"),
        ("user-2", "decision-1"),
        ("user-1", "decision-2"),
        ("user-2", "decision-2"),
    ],
    "rejections": [],
}


def _copy_mock_data() -> dict:
    """Mock 데이터 깊은 복사"""
    return copy.deepcopy(MOCK_DATA)


# =============================================================================
# MockKGRepository
# =============================================================================


class MockKGRepository:
    """테스트용 Mock KG Repository"""

    def __init__(self, data: dict | None = None):
        self.data = data if data is not None else _copy_mock_data()

    # =========================================================================
    # Meeting - 회의
    # =========================================================================

    async def update_meeting(self, meeting_id: str, data: dict) -> KGMeeting:
        """회의 업데이트"""
        if meeting_id not in self.data["meetings"]:
            raise ValueError(f"Meeting not found: {meeting_id}")

        self.data["meetings"][meeting_id].update(data)
        return await self.get_meeting(meeting_id)  # type: ignore

    async def get_meeting(self, meeting_id: str) -> KGMeeting | None:
        """회의 조회"""
        meeting = self.data["meetings"].get(meeting_id)
        if not meeting:
            return None

        team = self.data["teams"].get(meeting.get("team_id"))

        created_at = meeting.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return KGMeeting(
            id=meeting["id"],
            title=meeting.get("title", ""),
            status=meeting.get("status", ""),
            team_id=team.get("id") if team else None,
            team_name=team.get("name") if team else None,
            participant_ids=meeting.get("participant_ids", []),
            created_at=created_at,
        )

    # =========================================================================
    # Agenda - 아젠다
    # =========================================================================

    async def get_agenda(self, meeting_id: str) -> list[KGAgenda]:
        """회의의 아젠다 목록 조회"""
        agendas = [
            KGAgenda(
                id=a["id"],
                topic=a.get("topic", ""),
                description=a.get("description"),
                order=a.get("order", 0),
                meeting_id=meeting_id,
            )
            for a in self.data["agendas"].values()
            if a.get("meeting_id") == meeting_id
        ]
        return sorted(agendas, key=lambda x: x.order)

    # =========================================================================
    # Minutes - 회의록
    # =========================================================================

    async def create_minutes(
        self,
        meeting_id: str,
        summary: str,
        agenda_ids: list[str],
        decision_ids: list[str],
    ) -> KGMinutes:
        """회의록 생성"""
        minutes_id = f"minutes-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        self.data["minutes"][minutes_id] = {
            "id": minutes_id,
            "meeting_id": meeting_id,
            "summary": summary,
            "created_at": now.isoformat(),
            "agenda_ids": agenda_ids,
            "decision_ids": decision_ids,
        }

        return await self.get_minutes(meeting_id)  # type: ignore

    async def get_minutes(self, meeting_id: str) -> KGMinutes | None:
        """회의록 조회"""
        minutes = None
        for m in self.data["minutes"].values():
            if m.get("meeting_id") == meeting_id:
                minutes = m
                break

        if not minutes:
            return None

        # 결정사항 조회
        decision_ids = minutes.get("decision_ids", [])
        if not decision_ids:
            # decision_ids가 없으면 meeting의 agenda를 통해 찾기
            agendas = await self.get_agenda(meeting_id)
            agenda_ids = [a.id for a in agendas]
            decision_ids = [
                d["id"]
                for d in self.data["decisions"].values()
                if d.get("agenda_id") in agenda_ids
            ]

        decisions = []
        for did in decision_ids:
            d = self.data["decisions"].get(did)
            if d:
                agenda = self.data["agendas"].get(d.get("agenda_id", ""))
                decisions.append(
                    KGMinutesDecision(
                        id=d["id"],
                        content=d.get("content", ""),
                        context=d.get("context"),
                        agenda_topic=agenda.get("topic") if agenda else None,
                    )
                )

        # 액션아이템 조회
        action_items = []
        for ai in self.data["action_items"].values():
            if ai.get("decision_id") in decision_ids:
                assignee = self.data["users"].get(ai.get("assignee_id", ""))
                action_items.append(
                    KGMinutesActionItem(
                        id=ai["id"],
                        title=ai.get("title", ""),
                        description=ai.get("description"),
                        assignee=assignee.get("name") if assignee else None,
                        due_date=ai.get("due_date"),
                    )
                )

        created_at = minutes.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return KGMinutes(
            id=minutes["id"],
            meeting_id=meeting_id,
            summary=minutes.get("summary", ""),
            created_at=created_at or datetime.now(timezone.utc),
            decisions=decisions,
            action_items=action_items,
        )

    # =========================================================================
    # Decision - 결정사항
    # =========================================================================

    # --- 상태 변경 (승인/거절/머지) ---

    async def approve_decision(self, decision_id: str, user_id: str) -> bool:
        """결정 승인

        Returns:
            bool: 승인 성공 여부 (decision과 user가 존재하면 True)
        """
        if decision_id not in self.data["decisions"]:
            return False
        if user_id not in self.data["users"]:
            return False

        approval = (user_id, decision_id)
        if approval not in self.data["approvals"]:
            self.data["approvals"].append(approval)
        return True

    async def reject_decision(self, decision_id: str, user_id: str) -> bool:
        """결정 거절

        Returns:
            bool: 거절 성공 여부 (decision과 user가 존재하면 True)
        """
        if decision_id not in self.data["decisions"]:
            return False
        if user_id not in self.data["users"]:
            return False

        rejection = (user_id, decision_id)
        if rejection not in self.data["rejections"]:
            self.data["rejections"].append(rejection)
        return True

    async def merge_decision(self, decision_id: str) -> bool:
        """결정 머지

        Returns:
            bool: 머지 성공 여부 (decision이 존재하면 True)
        """
        if decision_id not in self.data["decisions"]:
            return False

        self.data["decisions"][decision_id]["status"] = "merged"
        self.data["decisions"][decision_id]["merged_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        return True

    # --- 조회 ---

    async def get_decision(self, decision_id: str) -> KGDecision | None:
        """결정사항 조회"""
        decision = self.data["decisions"].get(decision_id)
        if not decision:
            return None

        agenda = self.data["agendas"].get(decision.get("agenda_id", ""))
        meeting = None
        if agenda:
            meeting = self.data["meetings"].get(agenda.get("meeting_id", ""))

        approvers = [
            user_id for user_id, did in self.data["approvals"] if did == decision_id
        ]
        rejectors = [
            user_id for user_id, did in self.data["rejections"] if did == decision_id
        ]

        created_at = decision.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return KGDecision(
            id=decision["id"],
            content=decision.get("content", ""),
            status=decision.get("status", "pending"),
            context=decision.get("context"),
            created_at=created_at or datetime.now(timezone.utc),
            agenda_id=agenda.get("id") if agenda else None,
            agenda_topic=agenda.get("topic") if agenda else None,
            meeting_title=meeting.get("title") if meeting else None,
            approvers=approvers,
            rejectors=rejectors,
        )

    async def is_all_participants_approved(self, decision_id: str) -> bool:
        """모든 참여자 승인 여부 확인"""
        decision = self.data["decisions"].get(decision_id)
        if not decision:
            return False

        agenda = self.data["agendas"].get(decision.get("agenda_id", ""))
        if not agenda:
            return False

        meeting = self.data["meetings"].get(agenda.get("meeting_id", ""))
        if not meeting:
            return False

        participants = set(meeting.get("participant_ids", []))
        approvers = {
            user_id for user_id, did in self.data["approvals"] if did == decision_id
        }

        return participants == approvers
