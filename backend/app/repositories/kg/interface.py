"""KG Repository 인터페이스 정의

Protocol 기반 인터페이스로 구조적 서브타이핑 지원
"""

from typing import Protocol

from app.models.kg import KGAgenda, KGDecision, KGMeeting, KGMinutes


class IKGRepository(Protocol):
    """KG Repository 인터페이스

    KGRepository와 MockKGRepository가 구현하는 공통 인터페이스.
    Protocol을 사용하여 명시적 상속 없이 구조적 타이핑 지원.
    """

    async def get_meeting(self, meeting_id: str) -> KGMeeting | None:
        """회의 조회"""
        ...

    async def update_meeting(self, meeting_id: str, data: dict) -> KGMeeting:
        """회의 업데이트"""
        ...

    async def get_agenda(self, meeting_id: str) -> list[KGAgenda]:
        """회의의 아젠다 목록 조회"""
        ...

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

        Returns:
            KGMinutes (Projection)
        """
        ...

    async def get_minutes(self, meeting_id: str) -> KGMinutes | None:
        """회의록 조회"""
        ...

    async def get_decision(self, decision_id: str) -> KGDecision | None:
        """결정사항 조회"""
        ...

    async def reject_decision(self, decision_id: str, user_id: str) -> bool:
        """결정 거절"""
        ...

    async def is_all_participants_approved(self, decision_id: str) -> bool:
        """모든 참여자 승인 여부 확인"""
        ...

    async def merge_decision(self, decision_id: str) -> bool:
        """결정 머지"""
        ...

    async def approve_and_merge_if_complete(
        self, decision_id: str, user_id: str
    ) -> dict:
        """결정 승인 + 전원 승인 시 자동 머지 (원자적 트랜잭션)

        Returns:
            {
                "approved": bool,
                "merged": bool,
                "status": str,
                "approvers_count": int,
                "participants_count": int,
            }
        """
        ...
