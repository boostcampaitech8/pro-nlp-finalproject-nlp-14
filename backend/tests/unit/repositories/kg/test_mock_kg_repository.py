"""MockKGRepository 단위 테스트"""

import pytest

from app.repositories.kg.mock_repository import MockKGRepository


@pytest.fixture
def kg_repo():
    """테스트용 MockKGRepository (각 테스트마다 새 인스턴스)"""
    return MockKGRepository()


class TestMeetingOperations:
    """Meeting 관련 테스트"""

    @pytest.mark.asyncio
    async def test_get_meeting_exists(self, kg_repo):
        """존재하는 회의 조회"""
        meeting = await kg_repo.get_meeting("meeting-1")

        assert meeting is not None
        assert meeting.id == "meeting-1"
        assert meeting.title == "스프린트 계획 회의"
        assert meeting.status == "completed"
        assert meeting.team_id == "team-1"
        assert meeting.team_name == "개발팀"
        assert len(meeting.participant_ids) == 2

    @pytest.mark.asyncio
    async def test_get_meeting_not_found(self, kg_repo):
        """존재하지 않는 회의 조회"""
        meeting = await kg_repo.get_meeting("nonexistent")
        assert meeting is None

    @pytest.mark.asyncio
    async def test_update_meeting(self, kg_repo):
        """회의 업데이트"""
        updated = await kg_repo.update_meeting("meeting-1", {"status": "in_progress"})

        assert updated is not None
        assert updated.status == "in_progress"

    @pytest.mark.asyncio
    async def test_update_meeting_not_found(self, kg_repo):
        """존재하지 않는 회의 업데이트"""
        with pytest.raises(ValueError) as exc_info:
            await kg_repo.update_meeting("nonexistent", {"status": "in_progress"})

        assert "not found" in str(exc_info.value).lower()


class TestAgendaOperations:
    """Agenda 관련 테스트"""

    @pytest.mark.asyncio
    async def test_get_agenda(self, kg_repo):
        """아젠다 목록 조회"""
        agendas = await kg_repo.get_agenda("meeting-1")

        assert len(agendas) == 2
        # order 순으로 정렬되어 있어야 함
        assert agendas[0].order <= agendas[1].order

    @pytest.mark.asyncio
    async def test_get_agenda_empty(self, kg_repo):
        """아젠다가 없는 회의"""
        agendas = await kg_repo.get_agenda("nonexistent")
        assert agendas == []


class TestDecisionOperations:
    """Decision 관련 테스트"""

    @pytest.mark.asyncio
    async def test_get_decision(self, kg_repo):
        """결정사항 조회"""
        decision = await kg_repo.get_decision("decision-1")

        assert decision is not None
        assert decision.id == "decision-1"
        assert decision.content == "RESTful API 설계 원칙 준수"
        assert decision.status == "merged"

    @pytest.mark.asyncio
    async def test_get_decision_not_found(self, kg_repo):
        """존재하지 않는 결정사항 조회"""
        decision = await kg_repo.get_decision("nonexistent")
        assert decision is None

    @pytest.mark.asyncio
    async def test_approve_decision(self, kg_repo):
        """결정 승인"""
        # decision-3은 아직 승인되지 않은 상태
        result = await kg_repo.approve_decision("decision-3", "user-1")
        decision = await kg_repo.get_decision("decision-3")

        assert result is True
        assert "user-1" in decision.approvers

    @pytest.mark.asyncio
    async def test_approve_decision_not_found(self, kg_repo):
        """존재하지 않는 결정 승인"""
        result = await kg_repo.approve_decision("nonexistent", "user-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_approve_decision_duplicate(self, kg_repo):
        """중복 승인은 무시"""
        await kg_repo.approve_decision("decision-3", "user-1")
        await kg_repo.approve_decision("decision-3", "user-1")
        decision = await kg_repo.get_decision("decision-3")

        # 중복 없이 1개만 있어야 함
        assert decision.approvers.count("user-1") == 1

    @pytest.mark.asyncio
    async def test_reject_decision(self, kg_repo):
        """결정 거절"""
        result = await kg_repo.reject_decision("decision-3", "user-1")
        decision = await kg_repo.get_decision("decision-3")

        assert result is True
        assert "user-1" in decision.rejectors

    @pytest.mark.asyncio
    async def test_reject_decision_not_found(self, kg_repo):
        """존재하지 않는 결정 거절"""
        result = await kg_repo.reject_decision("nonexistent", "user-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_all_participants_approved_true(self, kg_repo):
        """모든 참여자 승인 여부 - decision-1은 이미 모두 승인됨"""
        result = await kg_repo.is_all_participants_approved("decision-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_all_participants_approved_false(self, kg_repo):
        """일부만 승인된 경우"""
        result = await kg_repo.is_all_participants_approved("decision-3")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_all_participants_approved_after_all_approve(self, kg_repo):
        """모든 참여자가 승인한 후"""
        # decision-3은 meeting-2에 속하고, 참여자는 user-1, user-2, user-3
        await kg_repo.approve_decision("decision-3", "user-1")
        await kg_repo.approve_decision("decision-3", "user-2")
        await kg_repo.approve_decision("decision-3", "user-3")

        result = await kg_repo.is_all_participants_approved("decision-3")
        assert result is True

    @pytest.mark.asyncio
    async def test_merge_decision(self, kg_repo):
        """결정 머지"""
        result = await kg_repo.merge_decision("decision-3")
        decision = await kg_repo.get_decision("decision-3")

        assert result is True
        assert decision.status == "merged"

    @pytest.mark.asyncio
    async def test_merge_nonexistent_decision(self, kg_repo):
        """존재하지 않는 결정 머지"""
        result = await kg_repo.merge_decision("nonexistent")
        assert result is False


class TestMinutesOperations:
    """Minutes 관련 테스트"""

    @pytest.mark.asyncio
    async def test_get_minutes(self, kg_repo):
        """회의록 조회"""
        minutes = await kg_repo.get_minutes("meeting-1")

        assert minutes is not None
        assert minutes.meeting_id == "meeting-1"
        assert "스프린트 계획" in minutes.summary
        assert len(minutes.decisions) > 0

    @pytest.mark.asyncio
    async def test_get_minutes_not_found(self, kg_repo):
        """존재하지 않는 회의록 조회"""
        minutes = await kg_repo.get_minutes("nonexistent")
        assert minutes is None

    @pytest.mark.asyncio
    async def test_create_minutes(self, kg_repo):
        """회의록 생성 (원홉)"""
        minutes = await kg_repo.create_minutes(
            meeting_id="meeting-2",
            summary="테스트 회의록 요약",
            agendas=[
                {
                    "topic": "새 아젠다",
                    "description": "테스트용 아젠다",
                    "decisions": [
                        {"content": "테스트 결정1", "context": "맥락1"},
                        {"content": "테스트 결정2", "context": "맥락2"},
                    ],
                }
            ],
        )

        assert minutes is not None
        assert minutes.meeting_id == "meeting-2"
        assert "테스트 회의록" in minutes.summary
        assert len(minutes.decisions) == 2

        # 다시 조회해도 같은 결과
        retrieved = await kg_repo.get_minutes("meeting-2")
        assert retrieved is not None
        assert retrieved.meeting_id == "meeting-2"
        assert len(retrieved.decisions) == 2

    @pytest.mark.asyncio
    async def test_create_minutes_multiple_agendas(self, kg_repo):
        """여러 아젠다가 있는 회의록 생성"""
        minutes = await kg_repo.create_minutes(
            meeting_id="meeting-2",
            summary="복수 아젠다 회의",
            agendas=[
                {
                    "topic": "아젠다1",
                    "description": "",
                    "decisions": [{"content": "결정A", "context": ""}],
                },
                {
                    "topic": "아젠다2",
                    "description": "",
                    "decisions": [
                        {"content": "결정B", "context": ""},
                        {"content": "결정C", "context": ""},
                    ],
                },
            ],
        )

        assert minutes is not None
        assert len(minutes.decisions) == 3  # 3개 결정

    @pytest.mark.asyncio
    async def test_create_minutes_empty_agendas(self, kg_repo):
        """빈 아젠다 목록으로 회의록 생성"""
        # 새 meeting 추가 (기존 decision과 연관 없음)
        kg_repo.data["meetings"]["meeting-new"] = {
            "id": "meeting-new",
            "title": "새 회의",
            "status": "completed",
            "team_id": "team-1",
            "participant_ids": ["user-1"],
            "created_at": "2026-01-26T09:00:00+00:00",
        }

        minutes = await kg_repo.create_minutes(
            meeting_id="meeting-new",
            summary="아젠다 없는 회의",
            agendas=[],
        )

        assert minutes is not None
        assert minutes.summary == "아젠다 없는 회의"
        assert len(minutes.decisions) == 0


class TestDataIsolation:
    """데이터 격리 테스트"""

    @pytest.mark.asyncio
    async def test_each_repo_has_own_data(self):
        """각 Repository 인스턴스는 독립적인 데이터를 가짐"""
        repo1 = MockKGRepository()
        repo2 = MockKGRepository()

        # repo1에서 수정
        await repo1.merge_decision("decision-3")

        # repo2에서는 변경되지 않음
        decision1 = await repo1.get_decision("decision-3")
        decision2 = await repo2.get_decision("decision-3")

        assert decision1.status == "merged"
        assert decision2.status == "pending"
