"""Mock Meeting Repository - 회의/안건 관련"""

from datetime import datetime
from typing import Any

from app.infrastructure.neo4j.interfaces import IMeetingRepository
from app.infrastructure.neo4j.mock.data import MOCK_DATA


class MockMeetingRepository(IMeetingRepository):
    """Mock 회의 저장소

    회의, 안건, 회의록 관련 조회 및 생성 기능.
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

    async def get_meeting_minutes(self, meeting_id: str) -> dict | None:
        """회의록(Minutes) 조회 - Decision Extractor 결과물

        Args:
            meeting_id: 회의 ID

        Returns:
            회의록 (summary, decisions, action_items 포함)
            회의록이 없으면 None
        """
        for minutes in self.data.get("minutes", {}).values():
            if minutes.get("meeting_id") == meeting_id:
                return {
                    "id": minutes["id"],
                    "meeting_id": minutes["meeting_id"],
                    "summary": minutes["summary"],
                    "decisions": minutes["decisions"],
                    "action_items": minutes["action_items"],
                    "created_at": minutes.get("created_at"),
                }
        return None

    async def list_meeting_minutes(self, team_id: str | None = None) -> list[dict]:
        """회의록 목록 조회

        Args:
            team_id: 팀 ID (선택적 필터)

        Returns:
            회의록 목록
        """
        results = []
        for minutes in self.data.get("minutes", {}).values():
            meeting = self.data["meetings"].get(minutes.get("meeting_id"))
            if not meeting:
                continue

            # 팀 필터
            if team_id and meeting.get("team_id") != team_id:
                continue

            results.append({
                "id": minutes["id"],
                "meeting_id": minutes["meeting_id"],
                "meeting_title": meeting["title"],
                "summary": minutes["summary"],
                "decision_count": len(minutes.get("decisions", [])),
                "action_item_count": len(minutes.get("action_items", [])),
                "created_at": minutes.get("created_at"),
            })

        # 최신순 정렬
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    async def create_agenda(
        self,
        meeting_id: str,
        agenda_id: str,
        topic: str,
        description: str | None = None,
    ) -> dict:
        """안건 노드 생성 + CONTAINS 관계

        Args:
            meeting_id: 회의 ID
            agenda_id: 안건 ID
            topic: 안건 주제
            description: 안건 설명

        Returns:
            생성된 안건 dict
        """
        agenda = {
            "id": agenda_id,
            "topic": topic,
            "description": description,
            "meeting_id": meeting_id,
            "created_at": datetime.now().isoformat(),
        }
        self.data["agendas"][agenda_id] = agenda
        return agenda
