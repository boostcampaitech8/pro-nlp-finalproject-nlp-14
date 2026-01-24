"""Mock User Repository - 사용자 활동 관련"""

from typing import Any

from app.infrastructure.neo4j.interfaces import IUserRepository
from app.infrastructure.neo4j.mock.data import MOCK_DATA


class MockUserRepository(IUserRepository):
    """Mock 사용자 저장소

    사용자 활동 통계 및 할당된 액션아이템 관련 조회 기능.
    """

    def __init__(self, data: dict[str, Any] | None = None):
        self.data = data if data is not None else MOCK_DATA

    async def get_user_activity(self, user_id: str) -> dict:
        """사용자 활동 요약

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 활동 통계 (팀/회의/액션아이템 수)
        """
        user = self.data["users"].get(user_id)
        if not user:
            return {}

        # 소속 팀 수
        team_count = sum(
            1 for m in self.data.get("member_of", [])
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
