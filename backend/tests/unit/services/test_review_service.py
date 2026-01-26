"""ReviewService 단위 테스트"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.review_service import ReviewService
from app.repositories.kg.mock_repository import MockKGRepository, _copy_mock_data


class TestReviewService:
    """ReviewService 테스트"""

    @pytest.fixture
    def mock_data(self):
        """테스트용 Mock 데이터"""
        return _copy_mock_data()

    @pytest.fixture
    def mock_kg_repo(self, mock_data):
        """MockKGRepository 인스턴스"""
        return MockKGRepository(mock_data)

    @pytest.fixture
    def mock_arq_pool(self):
        """Mock ARQ 연결 풀"""
        pool = AsyncMock()
        pool.enqueue_job = AsyncMock()
        pool.close = AsyncMock()
        return pool

    @pytest.fixture
    def review_service(self, mock_kg_repo):
        """ReviewService 인스턴스 (mock repo 주입)"""
        # Mock 드라이버 (실제로 사용하지 않음)
        mock_driver = MagicMock()
        service = ReviewService(mock_driver)
        # KG repo를 mock으로 교체
        service.kg_repo = mock_kg_repo
        return service

    # =========================================================================
    # create_review - approve
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_review_approve_success(self, review_service, mock_data):
        """승인 리뷰 생성 테스트 - 성공"""
        # meeting-1의 참여자: user-1, user-2
        # decision-3은 meeting-2에 속함 (참여자: user-1, user-2, user-3)
        decision_id = "decision-3"
        user_id = "user-1"

        response = await review_service.create_review(
            decision_id=decision_id,
            user_id=user_id,
            action="approve",
        )

        assert response.decision_id == decision_id
        assert response.action == "approve"
        assert response.success is True
        assert response.merged is False  # 아직 전원 승인 아님
        assert response.approvers_count == 1
        assert response.participants_count == 3  # user-1, user-2, user-3

    @pytest.mark.asyncio
    async def test_create_review_approve_auto_merge(
        self, review_service, mock_data, mock_arq_pool
    ):
        """승인 리뷰 생성 테스트 - 전원 승인 시 자동 머지"""
        # meeting-1의 참여자: user-1, user-2
        # decision-1에 대해 user-1, user-2가 이미 승인함 (MOCK_DATA 참조)
        # 새 decision 생성해서 테스트

        # decision-3은 meeting-2에 속함 (참여자: user-1, user-2, user-3)
        decision_id = "decision-3"

        with patch(
            "app.services.review_service.get_arq_pool",
            return_value=mock_arq_pool,
        ):
            # user-1 승인
            await review_service.create_review(
                decision_id=decision_id,
                user_id="user-1",
                action="approve",
            )

            # user-2 승인
            await review_service.create_review(
                decision_id=decision_id,
                user_id="user-2",
                action="approve",
            )

            # user-3 승인 - 전원 승인 완료 -> 자동 머지
            response = await review_service.create_review(
                decision_id=decision_id,
                user_id="user-3",
                action="approve",
            )

        assert response.merged is True
        assert response.status == "merged"
        assert response.approvers_count == 3
        assert response.participants_count == 3

    @pytest.mark.asyncio
    async def test_create_review_approve_not_found(self, review_service):
        """승인 리뷰 생성 테스트 - Decision 미존재"""
        with pytest.raises(ValueError, match="DECISION_NOT_FOUND"):
            await review_service.create_review(
                decision_id="non-existent-decision",
                user_id="user-1",
                action="approve",
            )

    # =========================================================================
    # create_review - reject
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_review_reject_success(self, review_service, mock_data):
        """거절 리뷰 생성 테스트 - 성공"""
        decision_id = "decision-3"
        user_id = "user-1"

        response = await review_service.create_review(
            decision_id=decision_id,
            user_id=user_id,
            action="reject",
        )

        assert response.decision_id == decision_id
        assert response.action == "reject"
        assert response.success is True
        assert response.merged is False

    @pytest.mark.asyncio
    async def test_create_review_reject_not_found(self, review_service):
        """거절 리뷰 생성 테스트 - Decision 미존재"""
        with pytest.raises(ValueError, match="DECISION_NOT_FOUND"):
            await review_service.create_review(
                decision_id="non-existent-decision",
                user_id="user-1",
                action="reject",
            )

    # =========================================================================
    # get_decision
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_decision_success(self, review_service):
        """결정 상세 조회 테스트 - 성공"""
        decision_id = "decision-1"

        response = await review_service.get_decision(decision_id)

        assert response.id == decision_id
        assert response.content == "RESTful API 설계 원칙 준수"
        assert response.status == "merged"
        assert "user-1" in response.approvers
        assert "user-2" in response.approvers

    @pytest.mark.asyncio
    async def test_get_decision_not_found(self, review_service):
        """결정 상세 조회 테스트 - 미존재"""
        with pytest.raises(ValueError, match="DECISION_NOT_FOUND"):
            await review_service.get_decision("non-existent-decision")

    # =========================================================================
    # get_meeting_decisions
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_meeting_decisions_success(self, review_service, mock_data):
        """회의 결정 목록 조회 테스트 - 성공"""
        meeting_id = "meeting-1"

        response = await review_service.get_meeting_decisions(meeting_id)

        assert response.meeting_id == meeting_id
        assert len(response.decisions) >= 1  # meeting-1에 속한 decision 수

    @pytest.mark.asyncio
    async def test_get_meeting_decisions_not_found(self, review_service):
        """회의 결정 목록 조회 테스트 - 회의 미존재"""
        with pytest.raises(ValueError, match="MEETING_NOT_FOUND"):
            await review_service.get_meeting_decisions("non-existent-meeting")

    # =========================================================================
    # mit-action 큐잉 테스트
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_review_approve_enqueues_mit_action_on_merge(
        self, review_service, mock_data, mock_arq_pool
    ):
        """머지 시 mit_action_task 큐잉 테스트"""
        decision_id = "decision-3"

        with patch(
            "app.services.review_service.get_arq_pool",
            return_value=mock_arq_pool,
        ):
            # 전원 승인하여 머지 트리거
            await review_service.create_review(
                decision_id=decision_id, user_id="user-1", action="approve"
            )
            await review_service.create_review(
                decision_id=decision_id, user_id="user-2", action="approve"
            )
            response = await review_service.create_review(
                decision_id=decision_id, user_id="user-3", action="approve"
            )

        # 머지 확인
        assert response.merged is True

        # mit_action_task 큐잉 확인
        mock_arq_pool.enqueue_job.assert_called_once_with(
            "mit_action_task", decision_id
        )
        mock_arq_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_review_approve_no_queue_without_merge(
        self, review_service, mock_data, mock_arq_pool
    ):
        """부분 승인 시 큐잉하지 않음 테스트"""
        decision_id = "decision-3"

        with patch(
            "app.services.review_service.get_arq_pool",
            return_value=mock_arq_pool,
        ):
            # 1명만 승인 (전원 승인 아님)
            response = await review_service.create_review(
                decision_id=decision_id, user_id="user-1", action="approve"
            )

        # 머지되지 않음
        assert response.merged is False

        # mit_action_task 큐잉되지 않음
        mock_arq_pool.enqueue_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_review_queue_failure_does_not_break_approve(
        self, review_service, mock_data
    ):
        """큐잉 실패해도 approve/merge는 성공"""
        decision_id = "decision-3"

        # 큐잉 실패하는 mock 설정
        failing_pool = AsyncMock()
        failing_pool.enqueue_job = AsyncMock(side_effect=Exception("Redis 연결 실패"))
        failing_pool.close = AsyncMock()

        with patch(
            "app.services.review_service.get_arq_pool",
            return_value=failing_pool,
        ):
            # 전원 승인
            await review_service.create_review(
                decision_id=decision_id, user_id="user-1", action="approve"
            )
            await review_service.create_review(
                decision_id=decision_id, user_id="user-2", action="approve"
            )
            response = await review_service.create_review(
                decision_id=decision_id, user_id="user-3", action="approve"
            )

        # 큐잉 실패해도 머지는 성공
        assert response.merged is True
        assert response.status == "merged"
