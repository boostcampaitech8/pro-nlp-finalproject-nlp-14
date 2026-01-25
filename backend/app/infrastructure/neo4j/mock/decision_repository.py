"""Mock Decision Repository - 결정사항/액션아이템 관련 (GT 시스템)"""

from datetime import datetime
from typing import Any

from app.infrastructure.neo4j.interfaces import IDecisionRepository
from app.infrastructure.neo4j.mock.data import MOCK_DATA


class MockDecisionRepository(IDecisionRepository):
    """Mock 결정사항 저장소

    Decision, ActionItem 관련 조회 및 생성 기능.
    회의 종료 후 GT 생성 워크플로우의 핵심 저장소.
    """

    def __init__(self, data: dict[str, Any] | None = None):
        self.data = data if data is not None else MOCK_DATA

    async def get_team_decisions(
        self, team_id: str, status: str = "latest"
    ) -> list[dict]:
        """팀의 결정사항(GT) 조회

        Args:
            team_id: 팀 ID
            status: 결정사항 상태 (기본: "latest")

        Returns:
            결정사항 목록 (회의, 안건 정보 포함)
        """
        # 팀의 회의 찾기
        team_meetings = [
            m for m in self.data["meetings"].values()
            if m.get("team_id") == team_id
        ]
        meeting_ids = [m["id"] for m in team_meetings]

        # 회의의 안건 찾기
        agendas = [
            a for a in self.data["agendas"].values()
            if a.get("meeting_id") in meeting_ids
        ]
        agenda_ids = [a["id"] for a in agendas]

        # 안건의 결정사항 찾기
        decisions = []
        for d in self.data["decisions"].values():
            if d.get("agenda_id") not in agenda_ids:
                continue
            if d.get("status") != status:
                continue

            # 관련 안건 및 회의 정보 찾기
            agenda = next(
                (a for a in agendas if a["id"] == d["agenda_id"]), None
            )
            meeting = next(
                (m for m in team_meetings if agenda and m["id"] == agenda.get("meeting_id")),
                None
            )

            decisions.append({
                "id": d["id"],
                "content": d["content"],
                "context": d.get("context"),
                "meeting_title": meeting["title"] if meeting else None,
                "agenda_topic": agenda["topic"] if agenda else None,
                "created_at": d.get("created_at"),
            })

        # 최신순 정렬
        decisions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return decisions

    async def search_decisions(
        self, query: str, team_id: str | None = None, limit: int = 10
    ) -> list[dict]:
        """결정사항 검색 (간단한 텍스트 매칭)

        Args:
            query: 검색어
            team_id: 팀 ID (선택적 필터)
            limit: 최대 결과 수

        Returns:
            매칭된 결정사항 목록
        """
        query_lower = query.lower()
        results = []

        for d in self.data["decisions"].values():
            if d.get("status") != "latest":
                continue

            # 간단한 텍스트 매칭
            content = d.get("content", "").lower()
            context = d.get("context", "").lower()

            if query_lower not in content and query_lower not in context:
                continue

            # 팀 필터
            if team_id:
                agenda = self.data["agendas"].get(d.get("agenda_id"))
                if agenda:
                    meeting = self.data["meetings"].get(agenda.get("meeting_id"))
                    if meeting and meeting.get("team_id") != team_id:
                        continue

            results.append({
                "id": d["id"],
                "content": d["content"],
                "context": d.get("context"),
                "created_at": d.get("created_at"),
            })

            if len(results) >= limit:
                break

        return results

    async def create_decision(
        self,
        agenda_id: str,
        decision_id: str,
        content: str,
        context: str | None = None,
    ) -> dict:
        """Decision 노드 생성 + HAS_DECISION 관계

        Args:
            agenda_id: 안건 ID (HAS_DECISION 관계의 시작점)
            decision_id: 결정사항 ID
            content: 결정 내용
            context: 결정 배경/맥락

        Returns:
            생성된 Decision dict
        """
        decision = {
            "id": decision_id,
            "content": content,
            "context": context,
            "status": "latest",
            "agenda_id": agenda_id,
            "created_at": datetime.now().isoformat(),
        }
        self.data["decisions"][decision_id] = decision
        return decision

    async def create_action_item(
        self,
        decision_id: str,
        action_item_id: str,
        title: str,
        assignee_id: str,
        description: str | None = None,
        due_date: str | None = None,
    ) -> dict:
        """ActionItem 노드 생성 + TRIGGERS, ASSIGNED_TO 관계

        Args:
            decision_id: 결정사항 ID (TRIGGERS 관계의 시작점)
            action_item_id: 액션아이템 ID
            title: 액션아이템 제목
            assignee_id: 담당자 ID (ASSIGNED_TO 관계)
            description: 상세 설명
            due_date: 마감일 (YYYY-MM-DD)

        Returns:
            생성된 ActionItem dict
        """
        action_item = {
            "id": action_item_id,
            "title": title,
            "description": description,
            "status": "pending",
            "due_date": due_date,
            "assignee_id": assignee_id,
            "decision_id": decision_id,
            "created_at": datetime.now().isoformat(),
        }
        self.data["action_items"][action_item_id] = action_item
        return action_item

    async def link_user_decision(
        self, user_id: str, decision_id: str, status: str = "approved"
    ) -> None:
        """REVIEWED 관계 생성

        Args:
            user_id: 사용자 ID
            decision_id: 결정사항 ID
            status: 리뷰 상태 (approved, rejected, pending)
        """
        # Mock에서는 reviewed 관계 리스트로 저장
        if "reviewed" not in self.data:
            self.data["reviewed"] = []

        self.data["reviewed"].append({
            "user_id": user_id,
            "decision_id": decision_id,
            "status": status,
            "responded_at": datetime.now().isoformat(),
        })
