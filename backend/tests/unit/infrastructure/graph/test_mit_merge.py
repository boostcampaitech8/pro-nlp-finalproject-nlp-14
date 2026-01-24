"""mit_merge 툴 단위 테스트

Phase1 PR Workflow의 결정사항 병합 툴 테스트.
다양한 시나리오를 통해 병합 성공/실패, SUPERSEDES 관계 생성 등을 검증.
"""

import pytest

from app.infrastructure.graph.tools.mit_merge import (
    MergeResult,
    execute_mit_merge,
    execute_mit_merge_batch,
    auto_merge_meeting_decisions,
)

# conftest.py에서 mock_data, repo, mock_get_graph_repo fixture 제공


# ===== execute_mit_merge 테스트 =====


class TestExecuteMitMerge:
    """단일 결정사항 병합 테스트"""

    @pytest.mark.asyncio
    async def test_merge_draft_to_latest_success(self, mock_get_graph_repo):
        """draft -> latest 병합 성공"""
        repo = mock_get_graph_repo

        # draft 결정사항 생성
        decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="병합 테스트 결정",
        )
        assert decision["status"] == "draft"

        # 병합 실행
        result = await execute_mit_merge(decision["id"])

        assert result.success is True
        assert result.decision_id == decision["id"]
        assert result.new_status == "latest"
        assert result.error is None

        # 상태 확인
        updated = await repo.get_decision(decision["id"])
        assert updated["status"] == "latest"

    @pytest.mark.asyncio
    async def test_merge_supersedes_previous_latest(self, mock_get_graph_repo):
        """이전 latest를 outdated로 대체"""
        repo = mock_get_graph_repo

        # decision-1은 agenda-1의 latest
        old_decision = await repo.get_decision("decision-1")
        assert old_decision["status"] == "latest"

        # 새 결정사항 생성 및 병합
        new_decision = await repo.create_decision(
            agenda_id="agenda-1",
            content="새로운 결정",
        )

        result = await execute_mit_merge(new_decision["id"])

        assert result.success is True
        assert result.superseded_decisions is not None
        assert len(result.superseded_decisions) == 1
        assert result.superseded_decisions[0]["id"] == "decision-1"

        # 이전 결정사항 상태 확인
        old_updated = await repo.get_decision("decision-1")
        assert old_updated["status"] == "outdated"

    @pytest.mark.asyncio
    async def test_merge_nonexistent_decision(self, mock_get_graph_repo):
        """존재하지 않는 결정사항 병합 시도"""
        result = await execute_mit_merge("nonexistent-decision")

        assert result.success is False
        assert result.decision_id == "nonexistent-decision"
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_merge_already_latest_decision(self, mock_get_graph_repo):
        """이미 latest인 결정사항 병합 시도"""
        # decision-1은 이미 latest
        result = await execute_mit_merge("decision-1")

        assert result.success is False
        assert "not in draft status" in result.error.lower()

    @pytest.mark.asyncio
    async def test_merge_outdated_decision(self, mock_get_graph_repo):
        """outdated 결정사항 병합 시도"""
        repo = mock_get_graph_repo

        # decision-1을 outdated로 변경
        decision = await repo.get_decision("decision-1")
        decision["status"] = "outdated"

        result = await execute_mit_merge("decision-1")

        assert result.success is False
        assert "not in draft status" in result.error.lower()


# ===== execute_mit_merge_batch 테스트 =====


class TestExecuteMitMergeBatch:
    """일괄 병합 테스트"""

    @pytest.mark.asyncio
    async def test_batch_merge_success(self, mock_get_graph_repo):
        """여러 결정사항 일괄 병합 성공"""
        repo = mock_get_graph_repo

        # 여러 draft 결정사항 생성
        d1 = await repo.create_decision(
            agenda_id="agenda-1",
            content="배치 결정 1",
        )
        d2 = await repo.create_decision(
            agenda_id="agenda-2",
            content="배치 결정 2",
        )

        # 일괄 병합
        results = await execute_mit_merge_batch([d1["id"], d2["id"]])

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_merge_partial_failure(self, mock_get_graph_repo):
        """일부 실패하는 일괄 병합"""
        repo = mock_get_graph_repo

        # draft 결정사항 하나
        d1 = await repo.create_decision(
            agenda_id="agenda-1",
            content="성공할 결정",
        )

        # 일괄 병합 (하나는 존재하지 않음)
        results = await execute_mit_merge_batch([d1["id"], "nonexistent"])

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False

    @pytest.mark.asyncio
    async def test_batch_merge_empty_list(self, mock_get_graph_repo):
        """빈 목록 일괄 병합"""
        results = await execute_mit_merge_batch([])

        assert len(results) == 0


# ===== auto_merge_meeting_decisions 테스트 =====


class TestAutoMergeMeetingDecisions:
    """회의 결정사항 자동 병합 테스트"""

    @pytest.mark.asyncio
    async def test_auto_merge_all_drafts(self, mock_get_graph_repo):
        """회의의 모든 draft 결정사항 자동 병합"""
        repo = mock_get_graph_repo

        # 회의에 여러 draft 결정사항 생성
        await repo.create_decision(
            agenda_id="agenda-1",  # meeting-1
            content="자동 병합 1",
        )
        await repo.create_decision(
            agenda_id="agenda-2",  # meeting-1
            content="자동 병합 2",
        )

        # 자동 병합
        results = await auto_merge_meeting_decisions("meeting-1")

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_auto_merge_no_drafts(self, mock_get_graph_repo):
        """draft 결정사항이 없는 회의"""
        # meeting-1의 기존 결정사항들은 모두 latest
        results = await auto_merge_meeting_decisions("meeting-1")

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_auto_merge_nonexistent_meeting(self, mock_get_graph_repo):
        """존재하지 않는 회의"""
        results = await auto_merge_meeting_decisions("nonexistent-meeting")

        assert len(results) == 0


# ===== MergeResult 테스트 =====


class TestMergeResult:
    """MergeResult 데이터클래스 테스트"""

    def test_success_result(self):
        """성공 결과 생성"""
        result = MergeResult(
            success=True,
            decision_id="test-id",
            new_status="latest",
            superseded_decisions=[{"id": "old-id", "status": "outdated"}],
        )

        assert result.success is True
        assert result.decision_id == "test-id"
        assert result.new_status == "latest"
        assert result.error is None

    def test_failure_result(self):
        """실패 결과 생성"""
        result = MergeResult(
            success=False,
            decision_id="test-id",
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.new_status is None


# ===== 통합 시나리오 테스트 =====


class TestIntegrationScenarios:
    """실제 사용 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_full_pr_workflow(self, mock_get_graph_repo):
        """전체 PR 워크플로우 시나리오

        1. 회의에서 새 결정사항 생성 (draft)
        2. 병합 실행 (Phase1: 자동 승인)
        3. draft -> latest
        4. 이전 latest -> outdated (SUPERSEDES)
        5. 히스토리 추적
        """
        repo = mock_get_graph_repo

        # 1. 새 결정사항 생성
        new_decision = await repo.create_decision(
            agenda_id="agenda-1",  # 기존 decision-1이 latest인 안건
            content="예산 6천만원으로 상향 조정",
            context="시장 상황 변화 반영",
        )
        assert new_decision["status"] == "draft"

        # 2 & 3. 병합 실행
        result = await execute_mit_merge(new_decision["id"])
        assert result.success is True
        assert result.new_status == "latest"

        # 4. SUPERSEDES 확인
        assert len(result.superseded_decisions) == 1
        assert result.superseded_decisions[0]["id"] == "decision-1"

        old_decision = await repo.get_decision("decision-1")
        assert old_decision["status"] == "outdated"

        # 5. 히스토리 추적
        history = await repo.get_decision_history(new_decision["id"])
        assert len(history) == 2
        assert history[0]["content"] == "예산 6천만원으로 상향 조정"
        assert history[1]["content"] == "RESTful API 설계 원칙 준수"

    @pytest.mark.asyncio
    async def test_multiple_decisions_same_meeting(self, mock_get_graph_repo):
        """같은 회의의 여러 결정사항 처리

        서로 다른 안건에 대한 결정사항들은 독립적으로 처리
        """
        repo = mock_get_graph_repo

        # 서로 다른 안건에 대한 결정사항 생성
        d1 = await repo.create_decision(
            agenda_id="agenda-1",
            content="안건1 결정",
        )
        d2 = await repo.create_decision(
            agenda_id="agenda-2",
            content="안건2 결정",
        )

        # 각각 병합
        r1 = await execute_mit_merge(d1["id"])
        r2 = await execute_mit_merge(d2["id"])

        assert r1.success is True
        assert r2.success is True

        # d1은 decision-1을 대체 (agenda-1)
        assert len(r1.superseded_decisions) == 1

        # d2는 decision-2를 대체 (agenda-2)
        assert len(r2.superseded_decisions) == 1

    @pytest.mark.asyncio
    async def test_decision_evolution_chain(self, mock_get_graph_repo):
        """결정사항 진화 체인

        같은 안건에 대해 여러 번 결정이 변경되는 시나리오
        v1 -> v2 -> v3 순서로 진화
        """
        repo = mock_get_graph_repo

        # v2 생성 및 병합 (v1=decision-1 대체)
        v2 = await repo.create_decision(
            agenda_id="agenda-1",
            content="API 설계 v2",
        )
        await execute_mit_merge(v2["id"])

        # v3 생성 및 병합 (v2 대체)
        v3 = await repo.create_decision(
            agenda_id="agenda-1",
            content="API 설계 v3 (최종)",
        )
        result = await execute_mit_merge(v3["id"])

        assert result.success is True

        # 히스토리 확인: v3 -> v2 -> v1
        history = await repo.get_decision_history(v3["id"])
        assert len(history) == 3
        assert history[0]["content"] == "API 설계 v3 (최종)"
        assert history[1]["content"] == "API 설계 v2"
        assert history[2]["content"] == "RESTful API 설계 원칙 준수"

        # 상태 확인
        assert (await repo.get_decision(v3["id"]))["status"] == "latest"
        assert (await repo.get_decision(v2["id"]))["status"] == "outdated"
        assert (await repo.get_decision("decision-1"))["status"] == "outdated"
