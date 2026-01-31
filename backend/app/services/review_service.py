"""Decision 리뷰 서비스

Decision approve/reject 및 자동 머지 처리.
Suggestion/Comment CRUD 및 @mit 멘션 처리 포함.
"""

import logging
import re
from typing import Literal

from app.api.dependencies import get_arq_pool
from app.models.kg import KGComment, KGSuggestion
from app.repositories.kg.repository import KGRepository
from app.schemas.review import (
    DecisionListResponse,
    DecisionResponse,
    DecisionReviewResponse,
)
from neo4j import AsyncDriver

# @mit 멘션 패턴
MIT_MENTION_PATTERN = re.compile(r"@mit\b", re.IGNORECASE)

logger = logging.getLogger(__name__)


class ReviewService:
    """Decision 리뷰 서비스"""

    def __init__(self, driver: AsyncDriver):
        self.kg_repo = KGRepository(driver)

    async def create_review(
        self,
        decision_id: str,
        user_id: str,
        action: Literal["approve", "reject"],
    ) -> DecisionReviewResponse:
        """리뷰 생성 (approve 또는 reject)

        approve: 원자적 트랜잭션으로 승인 + 전원승인 시 자동 머지
        reject: REJECTED_BY 관계 생성
        """
        if action == "approve":
            result = await self.kg_repo.approve_and_merge_if_complete(
                decision_id, user_id
            )
            if not result["approved"]:
                raise ValueError("DECISION_NOT_FOUND")

            logger.info(
                f"Decision approved: decision={decision_id}, user={user_id}, "
                f"merged={result['merged']}"
            )

            # merged=True 시 mit-action 태스크 큐잉
            if result["merged"]:
                await self._enqueue_mit_action(decision_id)

            return DecisionReviewResponse(
                decision_id=decision_id,
                action="approve",
                success=True,
                merged=result["merged"],
                status=result["status"],
                approvers_count=result["approvers_count"],
                participants_count=result["participants_count"],
            )

        else:  # reject
            success = await self.kg_repo.reject_decision(decision_id, user_id)
            if not success:
                raise ValueError("DECISION_NOT_FOUND")

            decision = await self.kg_repo.get_decision(decision_id)
            logger.info(f"Decision rejected: decision={decision_id}, user={user_id}")

            return DecisionReviewResponse(
                decision_id=decision_id,
                action="reject",
                success=True,
                merged=False,
                status=decision.status if decision else "rejected",
                approvers_count=len(decision.approvers) if decision else 0,
                participants_count=0,  # reject에서는 참여자 수 미계산
            )

    async def _enqueue_mit_action(self, decision_id: str) -> None:
        """mit-action 태스크 큐잉

        머지된 Decision에서 Action Item을 추출하는 비동기 작업을 큐에 등록.
        큐잉 실패해도 approve/merge는 성공으로 처리됨 (best-effort).
        """
        try:
            pool = await get_arq_pool()
            await pool.enqueue_job("mit_action_task", decision_id)
            await pool.close()
            logger.info(f"mit_action_task enqueued: decision={decision_id}")
        except Exception as e:
            # 큐잉 실패해도 approve/merge는 성공으로 처리
            logger.error(f"Failed to enqueue mit_action_task: {e}")

    async def get_decision(self, decision_id: str) -> DecisionResponse:
        """결정 상세 조회"""
        decision = await self.kg_repo.get_decision(decision_id)

        if not decision:
            raise ValueError("DECISION_NOT_FOUND")

        return DecisionResponse(
            id=decision.id,
            content=decision.content,
            context=decision.context,
            status=decision.status,
            agenda_topic=decision.agenda_topic,
            meeting_title=decision.meeting_title,
            approvers=decision.approvers,
            rejectors=decision.rejectors,
            created_at=decision.created_at,
        )

    async def get_meeting_decisions(self, meeting_id: str) -> DecisionListResponse:
        """회의의 모든 결정 조회"""
        minutes = await self.kg_repo.get_minutes(meeting_id)

        if not minutes:
            raise ValueError("MEETING_NOT_FOUND")

        decisions = []
        for d in minutes.decisions:
            detail = await self.kg_repo.get_decision(d.id)
            if detail:
                decisions.append(
                    DecisionResponse(
                        id=detail.id,
                        content=detail.content,
                        context=detail.context,
                        status=detail.status,
                        agenda_topic=detail.agenda_topic,
                        meeting_title=detail.meeting_title,
                        approvers=detail.approvers,
                        rejectors=detail.rejectors,
                        created_at=detail.created_at,
                    )
                )

        return DecisionListResponse(
            meeting_id=meeting_id,
            decisions=decisions,
        )

    # =========================================================================
    # Suggestion 관련
    # =========================================================================

    async def create_suggestion(
        self, decision_id: str, user_id: str, content: str
    ) -> KGSuggestion:
        """Suggestion 생성 (새 Decision도 함께 생성)"""
        suggestion = await self.kg_repo.create_suggestion(decision_id, user_id, content)
        logger.info(
            f"Suggestion created: suggestion={suggestion.id}, "
            f"decision={decision_id}, new_decision={suggestion.created_decision_id}"
        )
        return suggestion

    # =========================================================================
    # Comment 관련
    # =========================================================================

    async def create_comment(
        self, decision_id: str, user_id: str, content: str
    ) -> KGComment:
        """Comment 생성 + @mit 멘션 감지 시 Agent 호출 큐잉"""
        comment = await self.kg_repo.create_comment(decision_id, user_id, content)
        logger.info(f"Comment created: comment={comment.id}, decision={decision_id}")

        # @mit 멘션 감지 시 ARQ 태스크 큐잉
        if MIT_MENTION_PATTERN.search(content):
            await self._enqueue_mit_mention(comment.id, decision_id, content)

        return comment

    async def create_reply(
        self, comment_id: str, user_id: str, content: str
    ) -> KGComment:
        """대댓글 생성 + @mit 멘션 감지 시 Agent 호출 큐잉"""
        reply = await self.kg_repo.create_reply(comment_id, user_id, content)
        logger.info(f"Reply created: reply={reply.id}, parent={comment_id}")

        # @mit 멘션 감지 시 ARQ 태스크 큐잉
        if MIT_MENTION_PATTERN.search(content):
            await self._enqueue_mit_mention(reply.id, reply.decision_id, content)

        return reply

    async def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """Comment 삭제 (작성자만 가능)"""
        deleted = await self.kg_repo.delete_comment(comment_id, user_id)
        if deleted:
            logger.info(f"Comment deleted: comment={comment_id}, user={user_id}")
        return deleted

    async def _enqueue_mit_mention(
        self, comment_id: str, decision_id: str, content: str
    ) -> None:
        """@mit 멘션 처리 태스크 큐잉

        Agent가 Decision 컨텍스트를 바탕으로 응답 생성 후
        system-mit-agent 사용자로 대댓글을 작성함.
        """
        try:
            pool = await get_arq_pool()
            await pool.enqueue_job(
                "process_mit_mention",
                comment_id=comment_id,
                decision_id=decision_id,
                content=content,
            )
            await pool.close()
            logger.info(f"mit_mention_task enqueued: comment={comment_id}")
        except Exception as e:
            # 큐잉 실패해도 Comment 생성은 성공으로 처리 (best-effort)
            logger.error(f"Failed to enqueue mit_mention_task: {e}")

    # =========================================================================
    # Decision CRUD 확장
    # =========================================================================

    async def update_decision(
        self, decision_id: str, user_id: str, content: str | None = None, context: str | None = None
    ) -> DecisionResponse:
        """Decision 수정"""
        data = {}
        if content is not None:
            data["content"] = content
        if context is not None:
            data["context"] = context

        decision = await self.kg_repo.update_decision(decision_id, user_id, data)
        logger.info(f"Decision updated: decision={decision_id}, user={user_id}")

        return DecisionResponse(
            id=decision.id,
            content=decision.content,
            context=decision.context,
            status=decision.status,
            agenda_topic=decision.agenda_topic,
            meeting_title=decision.meeting_title,
            approvers=decision.approvers,
            rejectors=decision.rejectors,
            created_at=decision.created_at,
        )

    async def delete_decision(self, decision_id: str, user_id: str) -> bool:
        """Decision 삭제 (전체 CASCADE)"""
        deleted = await self.kg_repo.delete_decision(decision_id, user_id)
        if deleted:
            logger.info(f"Decision deleted: decision={decision_id}, user={user_id}")
        return deleted
