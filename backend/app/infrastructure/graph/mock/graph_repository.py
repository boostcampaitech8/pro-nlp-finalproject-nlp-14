"""Mock Graph Repository - Neo4j 실제 연결 전 개발용"""

from typing import Any

from app.infrastructure.graph.mock.data import MOCK_DATA


class MockGraphRepository:
    """Mock 그래프 저장소

    Neo4j 연결 전 workflow 개발을 위한 Mock 구현체.
    실제 Neo4j 연결 시 동일 인터페이스로 전환 가능.
    """

    def __init__(self, data: dict[str, Any] | None = None):
        self.data = data if data is not None else MOCK_DATA

    async def get_meeting_with_context(self, meeting_id: str) -> dict | None:
        """회의와 관련 컨텍스트 조회

        Args:
            meeting_id: 회의 ID

        Returns:
            회의, 팀, 안건, 결정사항, 참여자 정보를 포함한 dict
            회의가 없으면 None
        """
        meeting = self.data["meetings"].get(meeting_id)
        if not meeting:
            return None

        team = self.data["teams"].get(meeting.get("team_id"))
        participants = [
            self.data["users"].get(uid)
            for uid in meeting.get("participant_ids", [])
            if self.data["users"].get(uid)
        ]

        # 회의에 속한 안건들
        agendas = [
            a for a in self.data["agendas"].values()
            if a.get("meeting_id") == meeting_id
        ]

        # 안건에 속한 최신 결정사항들
        agenda_ids = [a["id"] for a in agendas]
        decisions = [
            d for d in self.data["decisions"].values()
            if d.get("agenda_id") in agenda_ids and d.get("status") == "latest"
        ]

        return {
            "meeting": meeting,
            "team": team,
            "agendas": agendas,
            "decisions": decisions,
            "participants": participants,
        }

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

    async def get_pending_action_items(self, user_id: str) -> list[dict]:
        """사용자의 미완료 액션아이템 조회

        Args:
            user_id: 사용자 ID

        Returns:
            미완료 액션아이템 목록
        """
        return [
            {
                "id": ai["id"],
                "title": ai["title"],
                "description": ai.get("description"),
                "status": ai["status"],
                "due_date": ai.get("due_date"),
                "from_decision": self.data["decisions"]
                    .get(ai.get("decision_id"), {})
                    .get("content"),
            }
            for ai in self.data["action_items"].values()
            if ai.get("assignee_id") == user_id
            and ai.get("status") in ["pending", "in_progress"]
        ]

    async def get_user_activity(self, user_id: str) -> dict:
        """사용자 활동 요약

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 활동 통계
        """
        user = self.data["users"].get(user_id)
        if not user:
            return {}

        # 소속 팀 수
        team_count = sum(
            1 for m in self.data["member_of"]
            if m.get("user_id") == user_id
        )

        # 참여 회의 수
        meeting_count = sum(
            1 for m in self.data["meetings"].values()
            if user_id in m.get("participant_ids", [])
        )

        # 할당된 액션아이템 수
        action_item_count = sum(
            1 for ai in self.data["action_items"].values()
            if ai.get("assignee_id") == user_id
        )

        return {
            "name": user["name"],
            "team_count": team_count,
            "meeting_count": meeting_count,
            "action_item_count": action_item_count,
        }

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
