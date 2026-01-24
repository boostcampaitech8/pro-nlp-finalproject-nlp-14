"""MockGraphRepository 단위 테스트

Phase1 PR Workflow의 Mock 그래프 저장소 테스트.
다양한 시나리오를 통해 결정사항 CRUD, 리뷰, SUPERSEDES 관계 등을 검증.
"""

import pytest

# conftest.py에서 mock_data, repo fixture 제공


# ===== 결정사항 생성 테스트 =====


class TestCreateDecision:
    """결정사항 생성 테스트"""

    @pytest.mark.asyncio
    async def test_create_decision_success(self, repo):
        """정상적인 결정사항 생성"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="새로운 결정사항",
            context="결정 배경 설명",
        )

        assert decision["id"].startswith("decision-")
        assert decision["content"] == "새로운 결정사항"
        assert decision["context"] == "결정 배경 설명"
        assert decision["status"] == "draft"
        assert decision["agenda_id"] == "agenda-1"
        assert "created_at" in decision

    @pytest.mark.asyncio
    async def test_create_decision_without_context(self, repo):
        """context 없이 결정사항 생성"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="컨텍스트 없는 결정",
        )

        assert decision["content"] == "컨텍스트 없는 결정"
        assert decision["context"] is None
        assert decision["status"] == "draft"

    @pytest.mark.asyncio
    async def test_create_decision_stored_in_data(self, repo, mock_data):
        """생성된 결정사항이 데이터에 저장되는지 확인"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="저장 확인용 결정",
        )

        stored = mock_data["decisions"].get(decision["id"])
        assert stored is not None
        assert stored["content"] == "저장 확인용 결정"


# ===== 결정사항 조회 테스트 =====


class TestGetDecision:
    """결정사항 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_existing_decision(self, repo):
        """존재하는 결정사항 조회"""
        decision = await repo.get_decision("decision-1")

        assert decision is not None
        assert decision["id"] == "decision-1"
        assert decision["content"] == "RESTful API 설계 원칙 준수"

    @pytest.mark.asyncio
    async def test_get_nonexistent_decision(self, repo):
        """존재하지 않는 결정사항 조회"""
        decision = await repo.get_decision("decision-nonexistent")

        assert decision is None


# ===== 리뷰 대기 결정사항 조회 테스트 =====


class TestGetDecisionsForReview:
    """리뷰 대기 결정사항 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_draft_decisions_for_meeting(self, repo):
        """회의의 draft 결정사항 조회"""
        # 먼저 draft 결정사항 생성
        await repo.create_decision(
            agenda_id="agenda-1",  # meeting-1에 속한 안건
            content="리뷰 대기 결정 1",
        )
        await repo.create_decision(
            agenda_id="agenda-2",  # meeting-1에 속한 안건
            content="리뷰 대기 결정 2",
        )

        drafts = await repo.get_decisions_for_review("meeting-1")

        assert len(drafts) == 2
        assert all(d["status"] == "draft" for d in drafts)

    @pytest.mark.asyncio
    async def test_no_draft_decisions(self, repo):
        """draft 결정사항이 없는 경우"""
        # 기본 데이터의 결정사항들은 모두 latest 상태
        drafts = await repo.get_decisions_for_review("meeting-1")

        assert len(drafts) == 0

    @pytest.mark.asyncio
    async def test_draft_decisions_include_agenda_topic(self, repo):
        """draft 결정사항에 안건 주제 포함 확인"""
        await repo.create_decision(
            agenda_id="agenda-1",
            content="안건 주제 확인용",
        )

        drafts = await repo.get_decisions_for_review("meeting-1")

        assert len(drafts) == 1
        assert drafts[0]["agenda_topic"] == "API 설계 검토"


# ===== 리뷰 테스트 =====


class TestReviewDecision:
    """결정사항 리뷰 테스트"""

    @pytest.mark.asyncio
    async def test_approve_decision(self, repo):
        """결정사항 승인"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="승인 테스트",
        )

        review = await repo.review_decision(
            decision_id=decision["id"],
            user_id="user-1",
            status="approved",
        )

        assert review["user_id"] == "user-1"
        assert review["decision_id"] == decision["id"]
        assert review["status"] == "approved"
        assert "responded_at" in review

    @pytest.mark.asyncio
    async def test_reject_decision(self, repo):
        """결정사항 거부"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="거부 테스트",
        )

        review = await repo.review_decision(
            decision_id=decision["id"],
            user_id="user-1",
            status="rejected",
        )

        assert review["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_update_existing_review(self, repo, mock_data):
        """기존 리뷰 업데이트"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="리뷰 업데이트 테스트",
        )

        # 첫 번째 리뷰 (rejected)
        await repo.review_decision(decision["id"], "user-1", "rejected")

        # 리뷰 변경 (approved)
        review = await repo.review_decision(decision["id"], "user-1", "approved")

        assert review["status"] == "approved"

        # 해당 결정사항에 대한 user-1의 리뷰는 하나만 있어야 함
        user1_reviews = [
            r for r in mock_data["reviews"]
            if r["decision_id"] == decision["id"] and r["user_id"] == "user-1"
        ]
        assert len(user1_reviews) == 1
        assert user1_reviews[0]["status"] == "approved"


# ===== 리뷰 목록 조회 테스트 =====


class TestGetDecisionReviews:
    """결정사항 리뷰 목록 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_reviews_with_user_info(self, repo):
        """리뷰 목록에 사용자 정보 포함 확인"""
        # decision-1은 이미 user-1, user-2의 리뷰가 있음
        reviews = await repo.get_decision_reviews("decision-1")

        assert len(reviews) == 2
        assert any(r["user_name"] == "김민준" for r in reviews)
        assert any(r["user_name"] == "이서연" for r in reviews)

    @pytest.mark.asyncio
    async def test_get_reviews_empty(self, repo):
        """리뷰가 없는 결정사항"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="리뷰 없는 결정",
        )

        reviews = await repo.get_decision_reviews(decision["id"])

        assert len(reviews) == 0


# ===== 참가자 승인 확인 테스트 =====


class TestCheckAllParticipantsApproved:
    """모든 참가자 승인 확인 테스트"""

    @pytest.mark.asyncio
    async def test_all_approved(self, repo):
        """모든 참가자가 승인한 경우"""
        # decision-1: meeting-1의 결정사항 (참가자: user-1, user-2)
        # 이미 둘 다 approved 상태
        all_approved, pending = await repo.check_all_participants_approved("decision-1")

        assert all_approved is True
        assert pending == []

    @pytest.mark.asyncio
    async def test_some_pending(self, repo):
        """일부 참가자만 승인한 경우"""
        # 새 결정사항 생성 (draft)
        decision = await repo.create_decision(
            agenda_id="agenda-1",  # meeting-1 (참가자: user-1, user-2)
            content="일부만 승인 테스트",
        )

        # user-1만 승인
        await repo.review_decision(decision["id"], "user-1", "approved")

        all_approved, pending = await repo.check_all_participants_approved(decision["id"])

        assert all_approved is False
        assert "user-2" in pending

    @pytest.mark.asyncio
    async def test_none_approved(self, repo):
        """아무도 승인하지 않은 경우"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",  # meeting-1 (참가자: user-1, user-2)
            content="아무도 승인 안함",
        )

        all_approved, pending = await repo.check_all_participants_approved(decision["id"])

        assert all_approved is False
        assert set(pending) == {"user-1", "user-2"}

    @pytest.mark.asyncio
    async def test_nonexistent_decision(self, repo):
        """존재하지 않는 결정사항"""
        all_approved, pending = await repo.check_all_participants_approved("nonexistent")

        assert all_approved is False
        assert pending == []


# ===== 결정사항 승격 테스트 =====


class TestPromoteDecisionToLatest:
    """결정사항 승격 테스트 (draft -> latest)"""

    @pytest.mark.asyncio
    async def test_promote_success(self, repo):
        """draft -> latest 승격 성공"""
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="승격 테스트",
        )
        assert decision["status"] == "draft"

        promoted = await repo.promote_decision_to_latest(decision["id"])

        assert promoted is not None
        assert promoted["status"] == "latest"

    @pytest.mark.asyncio
    async def test_promote_already_latest(self, repo):
        """이미 latest인 결정사항 승격 시도"""
        # decision-1은 이미 latest
        promoted = await repo.promote_decision_to_latest("decision-1")

        assert promoted is None

    @pytest.mark.asyncio
    async def test_promote_nonexistent(self, repo):
        """존재하지 않는 결정사항 승격 시도"""
        promoted = await repo.promote_decision_to_latest("nonexistent")

        assert promoted is None


# ===== SUPERSEDES 테스트 =====


class TestSupersedePreviousDecisions:
    """SUPERSEDES 관계 테스트"""

    @pytest.mark.asyncio
    async def test_supersede_previous_latest(self, repo, mock_data):
        """이전 latest를 outdated로 변경"""
        # decision-1은 agenda-1의 latest
        # 새 결정사항 생성 및 승격
        new_decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="새로운 API 설계 결정",
        )
        await repo.promote_decision_to_latest(new_decision["id"])

        # SUPERSEDES 처리
        superseded = await repo.supersede_previous_decisions(
            agenda_id="agenda-1",
            new_decision_id=new_decision["id"],
        )

        assert len(superseded) == 1
        assert superseded[0]["id"] == "decision-1"
        assert superseded[0]["status"] == "outdated"

        # SUPERSEDES 관계 확인
        supersedes_rel = mock_data["supersedes"]
        assert any(
            s["new_decision_id"] == new_decision["id"] and
            s["old_decision_id"] == "decision-1"
            for s in supersedes_rel
        )

    @pytest.mark.asyncio
    async def test_no_previous_latest(self, repo, mock_data):
        """이전 latest가 없는 경우"""
        # 새 안건에 첫 결정사항 생성
        mock_data["agendas"]["agenda-new"] = {
            "id": "agenda-new",
            "topic": "새 안건",
            "meeting_id": "meeting-1",
        }

        decision = await repo.create_decision(
            agenda_id="agenda-new",
            content="첫 결정사항",
        )
        await repo.promote_decision_to_latest(decision["id"])

        superseded = await repo.supersede_previous_decisions(
            agenda_id="agenda-new",
            new_decision_id=decision["id"],
        )

        assert len(superseded) == 0


# ===== 히스토리 추적 테스트 =====


class TestGetDecisionHistory:
    """결정사항 히스토리 추적 테스트 (mit_blame)"""

    @pytest.mark.asyncio
    async def test_history_single_decision(self, repo):
        """단일 결정사항 히스토리"""
        history = await repo.get_decision_history("decision-1")

        assert len(history) == 1
        assert history[0]["id"] == "decision-1"

    @pytest.mark.asyncio
    async def test_history_with_supersedes(self, repo):
        """SUPERSEDES 관계가 있는 히스토리"""
        # decision-1을 대체하는 새 결정사항 생성
        new_decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="대체 결정",
        )
        await repo.promote_decision_to_latest(new_decision["id"])
        await repo.supersede_previous_decisions("agenda-1", new_decision["id"])

        # 새 결정사항의 히스토리 추적
        history = await repo.get_decision_history(new_decision["id"])

        assert len(history) == 2
        assert history[0]["id"] == new_decision["id"]
        assert history[1]["id"] == "decision-1"

    @pytest.mark.asyncio
    async def test_history_chain(self, repo):
        """여러 단계의 SUPERSEDES 체인"""
        # decision-1 -> new-1 -> new-2 순서로 대체
        new1 = await repo.create_decision(
            agenda_id="agenda-1",
            content="두 번째 결정",
        )
        await repo.promote_decision_to_latest(new1["id"])
        await repo.supersede_previous_decisions("agenda-1", new1["id"])

        new2 = await repo.create_decision(
            agenda_id="agenda-1",
            content="세 번째 결정",
        )
        await repo.promote_decision_to_latest(new2["id"])
        await repo.supersede_previous_decisions("agenda-1", new2["id"])

        # 최신 결정사항에서 히스토리 추적
        history = await repo.get_decision_history(new2["id"])

        assert len(history) == 3
        assert history[0]["id"] == new2["id"]
        assert history[1]["id"] == new1["id"]
        assert history[2]["id"] == "decision-1"

    @pytest.mark.asyncio
    async def test_history_nonexistent(self, repo):
        """존재하지 않는 결정사항 히스토리"""
        history = await repo.get_decision_history("nonexistent")

        assert len(history) == 0


# ===== 회의 참가자 조회 테스트 =====


class TestGetMeetingParticipants:
    """회의 참가자 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_participants(self, repo):
        """회의 참가자 조회"""
        participants = await repo.get_meeting_participants("meeting-1")

        assert set(participants) == {"user-1", "user-2"}

    @pytest.mark.asyncio
    async def test_nonexistent_meeting(self, repo):
        """존재하지 않는 회의"""
        participants = await repo.get_meeting_participants("nonexistent")

        assert participants == []
