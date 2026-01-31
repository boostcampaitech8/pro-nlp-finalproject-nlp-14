"""KG Repository 인터페이스 정의

Protocol 기반 인터페이스로 구조적 서브타이핑 지원
"""

from typing import Protocol

from app.models.kg import (
    KGActionItem,
    KGAgenda,
    KGComment,
    KGDecision,
    KGMeeting,
    KGMinutes,
    KGSuggestion,
)


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
        """결정 승격 (draft -> latest, 기존 latest -> outdated)"""
        ...

    async def approve_and_merge_if_complete(
        self, decision_id: str, user_id: str
    ) -> dict:
        """결정 승인 + 전원 승인 시 자동 승격 (원자적 트랜잭션)

        전원 승인 시 동일 Agenda의 기존 latest -> outdated 처리됨.

        Returns:
            {
                "approved": bool,
                "merged": bool,  # latest 승격 여부
                "status": str,
                "approvers_count": int,
                "participants_count": int,
            }
        """
        ...

    # === Suggestion 관련 (신규) ===

    async def create_suggestion(
        self, decision_id: str, user_id: str, content: str
    ) -> KGSuggestion:
        """Suggestion + 새 Decision 생성 (원자적)

        Suggestion 생성 시 새 Decision도 함께 생성되며,
        원본 Decision의 Agenda에 연결됨.
        """
        ...

    # === Comment 관련 (신규) ===

    async def create_comment(
        self, decision_id: str, user_id: str, content: str
    ) -> KGComment:
        """Comment 생성

        (User)-[:COMMENTS]->(Comment) 관계로 생성됨.
        """
        ...

    async def create_reply(
        self, comment_id: str, user_id: str, content: str
    ) -> KGComment:
        """대댓글 생성

        (Reply)-[:REPLY_TO]->(ParentComment) 관계로 생성됨.
        """
        ...

    async def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """Comment 삭제 (작성자 확인 + CASCADE)

        작성자만 삭제 가능. 대댓글도 함께 삭제됨.
        """
        ...

    # === Decision CRUD 확장 (신규) ===

    async def update_decision(
        self, decision_id: str, user_id: str, data: dict
    ) -> KGDecision:
        """Decision 수정 (작성자 확인)"""
        ...

    async def delete_decision(self, decision_id: str, user_id: str) -> bool:
        """Decision 삭제 (작성자 확인 + 전체 CASCADE)

        REPLY_TO, TRIGGERS, CREATES, HAS_COMMENT 관계 모두 삭제.
        """
        ...

    # === Agenda CRUD (신규) ===

    async def update_agenda(
        self, agenda_id: str, user_id: str, data: dict
    ) -> KGAgenda:
        """Agenda 수정"""
        ...

    async def delete_agenda(self, agenda_id: str, user_id: str) -> bool:
        """Agenda 삭제 (전체 CASCADE)

        Agenda 하위의 모든 Decision, Comment, Suggestion 등 삭제.
        """
        ...

    # === ActionItem CRUD 확장 (신규) ===

    async def get_action_items(
        self, user_id: str | None = None, status: str | None = None
    ) -> list[KGActionItem]:
        """ActionItem 목록 조회 (필터링)"""
        ...

    async def update_action_item(
        self, action_item_id: str, user_id: str, data: dict
    ) -> KGActionItem:
        """ActionItem 수정"""
        ...

    async def delete_action_item(self, action_item_id: str, user_id: str) -> bool:
        """ActionItem 삭제"""
        ...

    # === Minutes View (신규) ===

    async def get_minutes_view(self, meeting_id: str) -> dict:
        """Minutes 전체 View 조회 (중첩 구조)

        Returns:
            {
                "meeting_id": str,
                "summary": str,
                "agendas": [{
                    "id": str,
                    "topic": str,
                    "description": str | None,
                    "order": int,
                    "decisions": [{
                        ...decision fields...,
                        "suggestions": [...],
                        "comments": [...]
                    }]
                }],
                "action_items": [...]
            }
        """
        ...
