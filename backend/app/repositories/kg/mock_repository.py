"""Mock KG Repository

테스트용 Mock Knowledge Graph 저장소.
"""

import copy
from datetime import datetime, timezone
from uuid import uuid4

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
            "status": "latest",
            "agenda_id": "agenda-1",
            "created_at": "2026-01-20T10:00:00+00:00",
        },
        "decision-2": {
            "id": "decision-2",
            "content": "1차 마일스톤: 2월 15일",
            "context": "MVP 기능 완성 목표",
            "status": "latest",
            "agenda_id": "agenda-2",
            "created_at": "2026-01-20T10:30:00+00:00",
        },
        "decision-3": {
            "id": "decision-3",
            "content": "JWT 기반 인증 채택",
            "context": "마이크로서비스 확장성과 stateless 특성 고려",
            "status": "draft",
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
    "suggestions": {},
    "comments": {},
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
        agendas: list[dict],
    ) -> KGMinutes:
        """회의록 생성 (원홉 - Meeting-Agenda-Decision 한 번에 생성)

        Args:
            meeting_id: 회의 ID
            summary: 회의 요약
            agendas: [{topic, description, decision: {content, context} | null}]
        """
        now = datetime.now(timezone.utc)

        # Meeting summary 업데이트
        if meeting_id in self.data["meetings"]:
            self.data["meetings"][meeting_id]["summary"] = summary

        # Agenda + Decision 생성
        agenda_ids = []
        decision_ids = []

        for idx, agenda_data in enumerate(agendas):
            agenda_id = f"agenda-{uuid4().hex[:8]}"
            self.data["agendas"][agenda_id] = {
                "id": agenda_id,
                "topic": agenda_data.get("topic", ""),
                "description": agenda_data.get("description", ""),
                "meeting_id": meeting_id,
                "order": idx,
            }
            agenda_ids.append(agenda_id)

            # Decision 생성 (decision이 있는 경우만)
            decision_data = agenda_data.get("decision")
            if decision_data:
                decision_id = f"decision-{uuid4().hex[:8]}"
                self.data["decisions"][decision_id] = {
                    "id": decision_id,
                    "content": decision_data.get("content", ""),
                    "context": decision_data.get("context", ""),
                    "status": "draft",
                    "agenda_id": agenda_id,
                    "created_at": now.isoformat(),
                }
                decision_ids.append(decision_id)

        # Minutes 메타데이터 저장 (Projection용)
        minutes_id = f"minutes-{meeting_id}"
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

        self.data["decisions"][decision_id]["status"] = "latest"
        self.data["decisions"][decision_id]["merged_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        return True

    async def approve_and_merge_if_complete(
        self, decision_id: str, user_id: str
    ) -> dict:
        """결정 승인 + 전원 승인 시 자동 머지

        Returns:
            dict: 승인/머지 결과
        """
        if decision_id not in self.data["decisions"]:
            return {"approved": False, "merged": False, "status": "not_found"}

        if user_id not in self.data["users"]:
            return {"approved": False, "merged": False, "status": "user_not_found"}

        decision = self.data["decisions"][decision_id]

        # 승인 관계 추가
        approval = (user_id, decision_id)
        if approval not in self.data["approvals"]:
            self.data["approvals"].append(approval)

        # 참여자 수 확인
        agenda = self.data["agendas"].get(decision.get("agenda_id", ""))
        if not agenda:
            return {
                "approved": True,
                "merged": False,
                "status": decision["status"],
                "approvers_count": 1,
                "participants_count": 0,
            }

        meeting = self.data["meetings"].get(agenda.get("meeting_id", ""))
        if not meeting:
            return {
                "approved": True,
                "merged": False,
                "status": decision["status"],
                "approvers_count": 1,
                "participants_count": 0,
            }

        participants = set(meeting.get("participant_ids", []))
        approvers = {
            uid for uid, did in self.data["approvals"] if did == decision_id
        }

        # 전원 승인 시 머지
        merged = participants == approvers and len(participants) > 0
        if merged:
            decision["status"] = "latest"
            decision["merged_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "approved": True,
            "merged": merged,
            "status": decision["status"],
            "approvers_count": len(approvers),
            "participants_count": len(participants),
        }

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
            status=decision.get("status", "draft"),
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

    # =========================================================================
    # Suggestion - 제안
    # =========================================================================

    async def create_suggestion(
        self, decision_id: str, user_id: str, content: str
    ) -> KGSuggestion:
        """Suggestion + 새 Decision 생성 (원자적)"""
        if decision_id not in self.data["decisions"]:
            raise ValueError(f"Decision not found: {decision_id}")
        if user_id not in self.data["users"]:
            raise ValueError(f"User not found: {user_id}")

        now = datetime.now(timezone.utc)
        original_decision = self.data["decisions"][decision_id]
        agenda_id = original_decision.get("agenda_id")

        # 새 Decision 생성
        new_decision_id = f"decision-{uuid4().hex[:8]}"
        self.data["decisions"][new_decision_id] = {
            "id": new_decision_id,
            "content": content,
            "context": None,
            "status": "draft",
            "agenda_id": agenda_id,
            "supersedes": decision_id,
            "created_at": now.isoformat(),
        }

        # Suggestion 생성
        suggestion_id = f"suggestion-{uuid4().hex[:8]}"
        self.data["suggestions"][suggestion_id] = {
            "id": suggestion_id,
            "content": content,
            "author_id": user_id,
            "decision_id": decision_id,
            "created_decision_id": new_decision_id,
            "created_at": now.isoformat(),
        }

        return KGSuggestion(
            id=suggestion_id,
            content=content,
            author_id=user_id,
            created_decision_id=new_decision_id,
            created_at=now,
        )

    # =========================================================================
    # Comment - 댓글
    # =========================================================================

    async def create_comment(
        self, decision_id: str, user_id: str, content: str
    ) -> KGComment:
        """Comment 생성"""
        if decision_id not in self.data["decisions"]:
            raise ValueError(f"Decision not found: {decision_id}")
        if user_id not in self.data["users"]:
            raise ValueError(f"User not found: {user_id}")

        now = datetime.now(timezone.utc)
        comment_id = f"comment-{uuid4().hex[:8]}"

        self.data["comments"][comment_id] = {
            "id": comment_id,
            "content": content,
            "author_id": user_id,
            "decision_id": decision_id,
            "parent_id": None,
            "created_at": now.isoformat(),
        }

        return KGComment(
            id=comment_id,
            content=content,
            author_id=user_id,
            decision_id=decision_id,
            parent_id=None,
            created_at=now,
        )

    async def create_reply(
        self, comment_id: str, user_id: str, content: str
    ) -> KGComment:
        """대댓글 생성"""
        if comment_id not in self.data["comments"]:
            raise ValueError(f"Comment not found: {comment_id}")
        if user_id not in self.data["users"]:
            raise ValueError(f"User not found: {user_id}")

        parent_comment = self.data["comments"][comment_id]
        now = datetime.now(timezone.utc)
        reply_id = f"comment-{uuid4().hex[:8]}"

        self.data["comments"][reply_id] = {
            "id": reply_id,
            "content": content,
            "author_id": user_id,
            "decision_id": parent_comment["decision_id"],
            "parent_id": comment_id,
            "created_at": now.isoformat(),
        }

        return KGComment(
            id=reply_id,
            content=content,
            author_id=user_id,
            decision_id=parent_comment["decision_id"],
            parent_id=comment_id,
            created_at=now,
        )

    async def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """Comment 삭제 (작성자 확인 + CASCADE)"""
        if comment_id not in self.data["comments"]:
            return False

        comment = self.data["comments"][comment_id]
        if comment["author_id"] != user_id:
            return False  # 작성자만 삭제 가능

        # 대댓글도 함께 삭제 (CASCADE)
        replies_to_delete = [
            cid
            for cid, c in self.data["comments"].items()
            if c.get("parent_id") == comment_id
        ]
        for reply_id in replies_to_delete:
            del self.data["comments"][reply_id]

        del self.data["comments"][comment_id]
        return True

    # =========================================================================
    # Decision CRUD 확장
    # =========================================================================

    async def update_decision(
        self, decision_id: str, user_id: str, data: dict
    ) -> KGDecision:
        """Decision 수정"""
        if decision_id not in self.data["decisions"]:
            raise ValueError(f"Decision not found: {decision_id}")

        # 필드 업데이트 (content, context만 수정 가능)
        decision = self.data["decisions"][decision_id]
        if "content" in data:
            decision["content"] = data["content"]
        if "context" in data:
            decision["context"] = data["context"]

        return await self.get_decision(decision_id)  # type: ignore

    async def delete_decision(self, decision_id: str, user_id: str) -> bool:
        """Decision 삭제 (전체 CASCADE)"""
        if decision_id not in self.data["decisions"]:
            return False

        # 관련 Comment 삭제
        comments_to_delete = [
            cid
            for cid, c in self.data["comments"].items()
            if c.get("decision_id") == decision_id
        ]
        for cid in comments_to_delete:
            del self.data["comments"][cid]

        # 관련 Suggestion 삭제
        suggestions_to_delete = [
            sid
            for sid, s in self.data["suggestions"].items()
            if s.get("decision_id") == decision_id
        ]
        for sid in suggestions_to_delete:
            # Suggestion이 생성한 Decision도 삭제
            created_decision_id = self.data["suggestions"][sid].get("created_decision_id")
            if created_decision_id and created_decision_id in self.data["decisions"]:
                del self.data["decisions"][created_decision_id]
            del self.data["suggestions"][sid]

        # 관련 ActionItem 삭제
        action_items_to_delete = [
            aid
            for aid, ai in self.data["action_items"].items()
            if ai.get("decision_id") == decision_id
        ]
        for aid in action_items_to_delete:
            del self.data["action_items"][aid]

        # Approval/Rejection 삭제
        self.data["approvals"] = [
            (uid, did) for uid, did in self.data["approvals"] if did != decision_id
        ]
        self.data["rejections"] = [
            (uid, did) for uid, did in self.data["rejections"] if did != decision_id
        ]

        del self.data["decisions"][decision_id]
        return True

    # =========================================================================
    # Agenda CRUD
    # =========================================================================

    async def update_agenda(
        self, agenda_id: str, user_id: str, data: dict
    ) -> KGAgenda:
        """Agenda 수정"""
        if agenda_id not in self.data["agendas"]:
            raise ValueError(f"Agenda not found: {agenda_id}")

        agenda = self.data["agendas"][agenda_id]
        if "topic" in data:
            agenda["topic"] = data["topic"]
        if "description" in data:
            agenda["description"] = data["description"]

        return KGAgenda(
            id=agenda["id"],
            topic=agenda.get("topic", ""),
            description=agenda.get("description"),
            order=agenda.get("order", 0),
            meeting_id=agenda.get("meeting_id"),
        )

    async def delete_agenda(self, agenda_id: str, user_id: str) -> bool:
        """Agenda 삭제 (전체 CASCADE)"""
        if agenda_id not in self.data["agendas"]:
            return False

        # 관련 Decision 찾기
        decisions_to_delete = [
            did
            for did, d in self.data["decisions"].items()
            if d.get("agenda_id") == agenda_id
        ]

        # 각 Decision과 관련된 엔티티 삭제
        for decision_id in decisions_to_delete:
            await self.delete_decision(decision_id, user_id)

        del self.data["agendas"][agenda_id]
        return True

    # =========================================================================
    # ActionItem CRUD 확장
    # =========================================================================

    async def get_action_items(
        self, user_id: str | None = None, status: str | None = None
    ) -> list[KGActionItem]:
        """ActionItem 목록 조회 (필터링)"""
        items = []
        for ai in self.data["action_items"].values():
            # 필터 적용
            if user_id and ai.get("assignee_id") != user_id:
                continue
            if status and ai.get("status") != status:
                continue

            due_date = ai.get("due_date")
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date)

            items.append(
                KGActionItem(
                    id=ai["id"],
                    title=ai.get("title", ""),
                    description=ai.get("description"),
                    status=ai.get("status", "pending"),
                    assignee_id=ai.get("assignee_id"),
                    due_date=due_date,
                    decision_id=ai.get("decision_id"),
                )
            )
        return items

    async def update_action_item(
        self, action_item_id: str, user_id: str, data: dict
    ) -> KGActionItem:
        """ActionItem 수정"""
        if action_item_id not in self.data["action_items"]:
            raise ValueError(f"ActionItem not found: {action_item_id}")

        ai = self.data["action_items"][action_item_id]
        for key in ["title", "description", "status", "assignee_id", "due_date"]:
            if key in data:
                ai[key] = data[key]

        due_date = ai.get("due_date")
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        return KGActionItem(
            id=ai["id"],
            title=ai.get("title", ""),
            description=ai.get("description"),
            status=ai.get("status", "pending"),
            assignee_id=ai.get("assignee_id"),
            due_date=due_date,
            decision_id=ai.get("decision_id"),
        )

    async def delete_action_item(self, action_item_id: str, user_id: str) -> bool:
        """ActionItem 삭제"""
        if action_item_id not in self.data["action_items"]:
            return False

        del self.data["action_items"][action_item_id]
        return True

    # =========================================================================
    # Minutes View
    # =========================================================================

    async def get_minutes_view(self, meeting_id: str) -> dict:
        """Minutes 전체 View 조회 (중첩 구조)"""
        meeting = self.data["meetings"].get(meeting_id)
        if not meeting:
            raise ValueError(f"Meeting not found: {meeting_id}")

        minutes = None
        for m in self.data["minutes"].values():
            if m.get("meeting_id") == meeting_id:
                minutes = m
                break

        # Agenda 조회
        agendas = []
        for a in sorted(
            [ag for ag in self.data["agendas"].values() if ag.get("meeting_id") == meeting_id],
            key=lambda x: x.get("order", 0),
        ):
            # Decision 조회
            decisions = []
            for d in self.data["decisions"].values():
                if d.get("agenda_id") != a["id"]:
                    continue

                # Suggestion 조회
                suggestions = []
                for s in self.data["suggestions"].values():
                    if s.get("decision_id") == d["id"]:
                        suggestions.append({
                            "id": s["id"],
                            "content": s["content"],
                            "author_id": s["author_id"],
                            "created_decision_id": s.get("created_decision_id"),
                            "created_at": s["created_at"],
                        })

                # Comment 조회 (최상위만, 대댓글은 중첩)
                comments = []
                for c in self.data["comments"].values():
                    if c.get("decision_id") == d["id"] and c.get("parent_id") is None:
                        # 대댓글 조회
                        replies = [
                            {
                                "id": r["id"],
                                "content": r["content"],
                                "author_id": r["author_id"],
                                "created_at": r["created_at"],
                            }
                            for r in self.data["comments"].values()
                            if r.get("parent_id") == c["id"]
                        ]
                        comments.append({
                            "id": c["id"],
                            "content": c["content"],
                            "author_id": c["author_id"],
                            "replies": replies,
                            "created_at": c["created_at"],
                        })

                created_at = d.get("created_at")
                decisions.append({
                    "id": d["id"],
                    "content": d.get("content", ""),
                    "context": d.get("context"),
                    "status": d.get("status", "draft"),
                    "created_at": created_at,
                    "suggestions": suggestions,
                    "comments": comments,
                })

            agendas.append({
                "id": a["id"],
                "topic": a.get("topic", ""),
                "description": a.get("description"),
                "order": a.get("order", 0),
                "decisions": decisions,
            })

        # ActionItem 조회
        action_items = []
        decision_ids = [d["id"] for a in agendas for d in a["decisions"]]
        for ai in self.data["action_items"].values():
            if ai.get("decision_id") in decision_ids:
                action_items.append({
                    "id": ai["id"],
                    "title": ai.get("title", ""),
                    "status": ai.get("status", "pending"),
                    "assignee_id": ai.get("assignee_id"),
                    "due_date": ai.get("due_date"),
                })

        return {
            "meeting_id": meeting_id,
            "summary": minutes.get("summary", "") if minutes else "",
            "agendas": agendas,
            "action_items": action_items,
        }
