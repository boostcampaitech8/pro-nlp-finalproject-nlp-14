"""Mock graph repository for Phase1 PR workflow."""

from datetime import datetime
from typing import Any

from app.infrastructure.neo4j.mock.data import MOCK_DATA


class MockGraphRepository:
    """Mock graph repository for decisions, reviews, and supersedes relations."""

    def __init__(self, data: dict[str, Any] | None = None):
        self.data = data if data is not None else MOCK_DATA

    def _now_iso(self) -> str:
        return datetime.now().isoformat()

    def _next_decision_id(self) -> str:
        max_id = 0
        for decision_id in self.data.get("decisions", {}).keys():
            if not decision_id.startswith("decision-"):
                continue
            suffix = decision_id.split("decision-", 1)[1]
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))
        return f"decision-{max_id + 1}"

    async def create_decision(
        self,
        agenda_id: str,
        content: str,
        context: str | None = None,
    ) -> dict:
        """Create a draft decision."""
        decision_id = self._next_decision_id()
        decision = {
            "id": decision_id,
            "agenda_id": agenda_id,
            "content": content,
            "context": context,
            "status": "draft",
            "created_at": self._now_iso(),
        }
        self.data.setdefault("decisions", {})[decision_id] = decision
        return decision

    async def get_decision(self, decision_id: str) -> dict | None:
        """Get a decision by id."""
        return self.data.get("decisions", {}).get(decision_id)

    async def get_decisions_for_review(self, meeting_id: str) -> list[dict]:
        """Return draft decisions for a meeting, with agenda topic."""
        results = []
        agendas = self.data.get("agendas", {})
        for decision in self.data.get("decisions", {}).values():
            if decision.get("status") != "draft":
                continue
            agenda = agendas.get(decision.get("agenda_id"))
            if not agenda:
                continue
            if agenda.get("meeting_id") != meeting_id:
                continue
            result = dict(decision)
            result["agenda_topic"] = agenda.get("topic")
            results.append(result)
        return results

    async def review_decision(self, decision_id: str, user_id: str, status: str) -> dict:
        """Create or update a decision review."""
        reviews = self.data.setdefault("reviews", [])
        for review in reviews:
            if review.get("decision_id") == decision_id and review.get("user_id") == user_id:
                review["status"] = status
                review["responded_at"] = self._now_iso()
                return review

        review = {
            "user_id": user_id,
            "decision_id": decision_id,
            "status": status,
            "responded_at": self._now_iso(),
        }
        reviews.append(review)
        return review

    async def get_decision_reviews(self, decision_id: str) -> list[dict]:
        """Return reviews for a decision with user info."""
        reviews = [
            review
            for review in self.data.get("reviews", [])
            if review.get("decision_id") == decision_id
        ]
        users = self.data.get("users", {})
        results = []
        for review in reviews:
            user = users.get(review.get("user_id"))
            result = dict(review)
            result["user_name"] = user.get("name") if user else None
            results.append(result)
        return results

    async def check_all_participants_approved(
        self, decision_id: str
    ) -> tuple[bool, list[str]]:
        """Check if all meeting participants approved a decision."""
        decision = self.data.get("decisions", {}).get(decision_id)
        if not decision:
            return False, []

        agenda = self.data.get("agendas", {}).get(decision.get("agenda_id"))
        if not agenda:
            return False, []

        meeting = self.data.get("meetings", {}).get(agenda.get("meeting_id"))
        if not meeting:
            return False, []

        participants = meeting.get("participant_ids", [])
        if not participants:
            return True, []

        review_map = {
            review.get("user_id"): review.get("status")
            for review in self.data.get("reviews", [])
            if review.get("decision_id") == decision_id
        }
        pending = [
            user_id
            for user_id in participants
            if review_map.get(user_id) != "approved"
        ]
        return len(pending) == 0, pending

    async def promote_decision_to_latest(self, decision_id: str) -> dict | None:
        """Promote a draft decision to latest."""
        decision = self.data.get("decisions", {}).get(decision_id)
        if not decision or decision.get("status") != "draft":
            return None
        decision["status"] = "latest"
        return decision

    async def supersede_previous_decisions(
        self, agenda_id: str, new_decision_id: str
    ) -> list[dict]:
        """Mark previous latest decisions as outdated and record supersedes."""
        decisions = self.data.get("decisions", {})
        supersedes = self.data.setdefault("supersedes", [])
        superseded = []

        for decision in decisions.values():
            if decision.get("agenda_id") != agenda_id:
                continue
            if decision.get("id") == new_decision_id:
                continue
            if decision.get("status") != "latest":
                continue

            decision["status"] = "outdated"
            superseded.append(decision)

            if not any(
                rel.get("new_decision_id") == new_decision_id
                and rel.get("old_decision_id") == decision.get("id")
                for rel in supersedes
            ):
                supersedes.append(
                    {
                        "new_decision_id": new_decision_id,
                        "old_decision_id": decision.get("id"),
                        "created_at": self._now_iso(),
                    }
                )

        return superseded

    async def get_decision_history(self, decision_id: str) -> list[dict]:
        """Trace a decision history via supersedes relationships."""
        decisions = self.data.get("decisions", {})
        if decision_id not in decisions:
            return []

        supersedes = self.data.get("supersedes", [])
        history = []
        current_id = decision_id
        seen = set()

        while current_id and current_id not in seen:
            decision = decisions.get(current_id)
            if not decision:
                break
            history.append(decision)
            seen.add(current_id)

            rel = next(
                (
                    rel
                    for rel in supersedes
                    if rel.get("new_decision_id") == current_id
                ),
                None,
            )
            if not rel:
                break
            current_id = rel.get("old_decision_id")

        return history

    async def get_meeting_participants(self, meeting_id: str) -> list[str]:
        """Return participant user ids for a meeting."""
        meeting = self.data.get("meetings", {}).get(meeting_id)
        if not meeting:
            return []
        return list(meeting.get("participant_ids", []))
