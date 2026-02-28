"""Decision 리뷰 서비스

Decision approve/reject 및 자동 머지 처리.
Suggestion/Comment CRUD 및 @mit 멘션 처리 포함.
"""

import logging
from typing import Literal

from app.api.dependencies import get_arq_pool
from app.constants.agents import has_agent_mention
from app.core.telemetry import get_mit_metrics
from app.models.kg import KGComment, KGSuggestion
from app.repositories.kg.repository import KGRepository
from app.schemas.review import (
    DecisionListResponse,
    DecisionResponse,
    DecisionReviewResponse,
)
from app.services.minutes_events import minutes_event_manager
from neo4j import AsyncDriver

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

            # 이미 rejected된 decision에 approve 시도
            if result.get("already_rejected"):
                raise ValueError("DECISION_ALREADY_REJECTED")

            if not result["approved"]:
                raise ValueError("DECISION_NOT_FOUND")

            logger.info(
                f"Decision approved: decision={decision_id}, user={user_id}, "
                f"merged={result['merged']}"
            )

            # merged=True 시 mit-action 태스크 큐잉
            if result["merged"]:
                await self._enqueue_mit_action(decision_id)

            # 이벤트 발행
            decision = await self.kg_repo.get_decision(decision_id)
            if decision:
                await self._publish_event(decision.meeting_id, {
                    "event": "decision_review_changed",
                    "decision_id": decision_id,
                    "action": action,
                    "merged": result["merged"],
                })

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
            result = await self.kg_repo.reject_decision(decision_id, user_id)
            if not result["rejected"]:
                raise ValueError("DECISION_NOT_FOUND")

            decision = await self.kg_repo.get_decision(decision_id)

            if result.get("already_finalized"):
                logger.info(
                    f"Decision reject attempted on finalized decision: "
                    f"decision={decision_id}, user={user_id}, status={result['status']}"
                )
            else:
                logger.info(
                    f"Decision rejected: decision={decision_id}, user={user_id}, "
                    f"status={result['status']}"
                )

            # 이벤트 발행
            if decision:
                await self._publish_event(decision.meeting_id, {
                    "event": "decision_review_changed",
                    "decision_id": decision_id,
                    "action": action,
                    "merged": False,
                    "status": result["status"],
                })

            return DecisionReviewResponse(
                decision_id=decision_id,
                action="reject",
                success=True,
                merged=False,
                status=result["status"],
                approvers_count=len(decision.approvers) if decision else 0,
                participants_count=0,
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

            # 메트릭 기록
            metrics = get_mit_metrics()
            if metrics:
                metrics.arq_task_enqueue_total.add(1, {"task_name": "mit_action_task"})

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
        self, decision_id: str, user_id: str, content: str, meeting_id: str
    ) -> KGSuggestion:
        """Suggestion 생성 + 즉시 draft Decision 생성

        워크플로우:
        1. Suggestion 노드 생성 (status: 'pending')
        2. 새 draft Decision 즉시 생성
        3. 기존 draft Decision → superseded
        4. AI 분석 태스크 큐잉 (선택적)
        """
        suggestion = await self.kg_repo.create_suggestion(
            decision_id, user_id, content, meeting_id
        )
        logger.info(
            f"Suggestion created: suggestion={suggestion.id}, "
            f"decision={decision_id}, new_decision={suggestion.created_decision_id}"
        )

        # AI 분석 태스크 큐잉 (선택적 - 필요 시)
        await self._enqueue_suggestion_analysis(suggestion.id, decision_id, content)

        # 이벤트 발행
        await self._publish_event(meeting_id, {
            "event": "suggestion_created",
            "decision_id": decision_id,
            "suggestion_id": suggestion.id,
            "created_decision_id": suggestion.created_decision_id,
        })

        return suggestion

    async def _enqueue_suggestion_analysis(
        self, suggestion_id: str, decision_id: str, content: str
    ) -> None:
        """Suggestion AI 분석 태스크 큐잉"""
        try:
            pool = await get_arq_pool()
            await pool.enqueue_job(
                "process_suggestion_task",
                suggestion_id=suggestion_id,
                decision_id=decision_id,
                content=content,
            )
            await pool.close()

            # 메트릭 기록
            metrics = get_mit_metrics()
            if metrics:
                metrics.arq_task_enqueue_total.add(1, {"task_name": "process_suggestion_task"})

            logger.info(f"process_suggestion_task enqueued: suggestion={suggestion_id}")
        except Exception as e:
            logger.error(f"Failed to enqueue process_suggestion_task: {e}")

    # =========================================================================
    # Comment 관련
    # =========================================================================

    async def create_comment(
        self, decision_id: str, user_id: str, content: str
    ) -> KGComment:
        """Comment 생성 + @mit 멘션 감지 시 Agent 호출 큐잉"""
        # @mit 멘션이 있으면 Agent 응답 대기 중
        has_mit_mention = has_agent_mention(content)
        comment = await self.kg_repo.create_comment(
            decision_id, user_id, content, pending_agent_reply=has_mit_mention
        )
        logger.info(f"Comment created: comment={comment.id}, decision={decision_id}")

        # @mit 멘션 감지 시 ARQ 태스크 큐잉
        if has_mit_mention:
            await self._enqueue_mit_mention(comment.id, decision_id, content)

        # 이벤트 발행 - decision에서 meeting_id 조회 필요
        decision = await self.kg_repo.get_decision(decision_id)
        if decision:
            await self._publish_event(decision.meeting_id, {
                "event": "comment_created",
                "decision_id": decision_id,
                "comment_id": comment.id,
            })

        return comment

    async def create_reply(
        self, comment_id: str, user_id: str, content: str
    ) -> KGComment:
        """대댓글 생성 + @mit 멘션 감지 시 Agent 호출 큐잉"""
        # @mit 멘션이 있으면 Agent 응답 대기 중
        has_mit_mention = has_agent_mention(content)
        reply = await self.kg_repo.create_reply(
            comment_id, user_id, content, pending_agent_reply=has_mit_mention
        )
        logger.info(f"Reply created: reply={reply.id}, parent={comment_id}")

        # @mit 멘션 감지 시 ARQ 태스크 큐잉
        if has_mit_mention:
            await self._enqueue_mit_mention(reply.id, reply.decision_id, content)

        # 이벤트 발행
        decision = await self.kg_repo.get_decision(reply.decision_id)
        if decision:
            await self._publish_event(decision.meeting_id, {
                "event": "comment_created",
                "decision_id": reply.decision_id,
                "comment_id": reply.id,
                "parent_id": comment_id,
            })

        return reply

    async def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """Comment 삭제 (작성자만 가능)"""
        result = await self.kg_repo.delete_comment(comment_id, user_id)
        if result:
            logger.info(f"Comment deleted: comment={comment_id}, user={user_id}")

            # 이벤트 발행
            await self._publish_event(result.get("meeting_id"), {
                "event": "comment_deleted",
                "decision_id": result.get("decision_id"),
                "comment_id": comment_id,
            })
            return True
        return False

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

            # 메트릭 기록
            metrics = get_mit_metrics()
            if metrics:
                metrics.arq_task_enqueue_total.add(1, {"task_name": "process_mit_mention"})

            logger.info(f"mit_mention_task enqueued: comment={comment_id}")
        except Exception as e:
            # 큐잉 실패해도 Comment 생성은 성공으로 처리 (best-effort)
            logger.error(f"Failed to enqueue mit_mention_task: {e}")

    async def _publish_event(self, meeting_id: str | None, event: dict) -> None:
        """Minutes 이벤트 발행 (best-effort)"""
        if not meeting_id:
            return
        try:
            await minutes_event_manager.publish(meeting_id, event)
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

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

        # 이벤트 발행
        await self._publish_event(decision.meeting_id, {
            "event": "decision_updated",
            "decision_id": decision_id,
        })

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
