"""Decision 리뷰 서비스

Decision approve/reject 및 자동 머지 처리
"""

import logging
from typing import Literal

from neo4j import AsyncDriver

from app.api.dependencies import get_arq_pool
from app.repositories.kg.repository import KGRepository
from app.schemas.review import (
    DecisionListResponse,
    DecisionResponse,
    DecisionReviewResponse,
)

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
