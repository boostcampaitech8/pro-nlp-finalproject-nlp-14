"""save_to_kg 노드 테스트"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.graph.workflows.generate_pr.nodes.persistence import save_to_kg
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState
from app.models.kg import KGMinutes, KGMinutesDecision


class TestSaveToKg:
    """save_to_kg 노드 테스트"""

    @pytest.mark.asyncio
    async def test_save_to_kg_no_meeting_id(self):
        """meeting_id가 없는 경우"""
        state = GeneratePrState(
            generate_pr_agendas=[{"topic": "테스트"}],
            generate_pr_summary="요약",
        )

        result = await save_to_kg(state)

        assert result.get("generate_pr_agenda_ids") == []
        assert result.get("generate_pr_decision_ids") == []

    @pytest.mark.asyncio
    async def test_save_to_kg_no_agendas(self):
        """agendas가 없는 경우"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_agendas=[],
            generate_pr_summary="요약",
        )

        result = await save_to_kg(state)

        assert result.get("generate_pr_agenda_ids") == []
        assert result.get("generate_pr_decision_ids") == []

    @pytest.mark.asyncio
    async def test_save_to_kg_success(self):
        """정상적인 저장"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_agendas=[
                {
                    "topic": "API 설계",
                    "description": "설명",
                    "decisions": [
                        {"content": "결정1", "context": "맥락1"},
                        {"content": "결정2", "context": "맥락2"},
                    ],
                }
            ],
            generate_pr_summary="회의 요약",
        )

        mock_minutes = KGMinutes(
            id="minutes-meeting-1",
            meeting_id="meeting-1",
            summary="회의 요약",
            created_at=datetime.now(timezone.utc),
            decisions=[
                KGMinutesDecision(id="decision-1", content="결정1", context="맥락1"),
                KGMinutesDecision(id="decision-2", content="결정2", context="맥락2"),
            ],
            action_items=[],
        )

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.persistence.get_neo4j_driver"
        ) as mock_get_driver:
            mock_driver = MagicMock()
            mock_get_driver.return_value = mock_driver

            with patch(
                "app.infrastructure.graph.workflows.generate_pr.nodes.persistence.KGRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.create_minutes = AsyncMock(return_value=mock_minutes)
                mock_repo_class.return_value = mock_repo

                result = await save_to_kg(state)

        # create_minutes 호출 확인
        mock_repo.create_minutes.assert_called_once_with(
            meeting_id="meeting-1",
            summary="회의 요약",
            agendas=[
                {
                    "topic": "API 설계",
                    "description": "설명",
                    "decisions": [
                        {"content": "결정1", "context": "맥락1"},
                        {"content": "결정2", "context": "맥락2"},
                    ],
                }
            ],
        )

        # 결과 확인
        decision_ids = result.get("generate_pr_decision_ids", [])
        assert len(decision_ids) == 2
        assert "decision-1" in decision_ids
        assert "decision-2" in decision_ids

    @pytest.mark.asyncio
    async def test_save_to_kg_error(self):
        """저장 에러 처리"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_agendas=[{"topic": "테스트", "decisions": []}],
            generate_pr_summary="요약",
        )

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.persistence.get_neo4j_driver"
        ) as mock_get_driver:
            mock_driver = MagicMock()
            mock_get_driver.return_value = mock_driver

            with patch(
                "app.infrastructure.graph.workflows.generate_pr.nodes.persistence.KGRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.create_minutes = AsyncMock(
                    side_effect=Exception("DB Error")
                )
                mock_repo_class.return_value = mock_repo

                result = await save_to_kg(state)

        # 에러 시 빈 결과 반환
        assert result.get("generate_pr_agenda_ids") == []
        assert result.get("generate_pr_decision_ids") == []

    @pytest.mark.asyncio
    async def test_save_to_kg_multiple_agendas(self):
        """여러 아젠다 저장"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_agendas=[
                {
                    "topic": "아젠다1",
                    "description": "",
                    "decisions": [{"content": "결정1", "context": ""}],
                },
                {
                    "topic": "아젠다2",
                    "description": "",
                    "decisions": [
                        {"content": "결정2", "context": ""},
                        {"content": "결정3", "context": ""},
                    ],
                },
            ],
            generate_pr_summary="여러 아젠다 회의",
        )

        mock_minutes = KGMinutes(
            id="minutes-meeting-1",
            meeting_id="meeting-1",
            summary="여러 아젠다 회의",
            created_at=datetime.now(timezone.utc),
            decisions=[
                KGMinutesDecision(id="d1", content="결정1"),
                KGMinutesDecision(id="d2", content="결정2"),
                KGMinutesDecision(id="d3", content="결정3"),
            ],
            action_items=[],
        )

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.persistence.get_neo4j_driver"
        ) as mock_get_driver:
            mock_get_driver.return_value = MagicMock()

            with patch(
                "app.infrastructure.graph.workflows.generate_pr.nodes.persistence.KGRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.create_minutes = AsyncMock(return_value=mock_minutes)
                mock_repo_class.return_value = mock_repo

                result = await save_to_kg(state)

        decision_ids = result.get("generate_pr_decision_ids", [])
        assert len(decision_ids) == 3
