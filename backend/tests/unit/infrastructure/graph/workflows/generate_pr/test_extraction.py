"""extract_agendas 노드 테스트"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.graph.workflows.generate_pr.nodes.extraction import (
    AgendaData,
    DecisionData,
    ExtractionOutput,
    extract_agendas,
)
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState


class TestExtractAgendas:
    """extract_agendas 노드 테스트"""

    @pytest.mark.asyncio
    async def test_extract_agendas_empty_transcript(self):
        """빈 트랜스크립트 처리"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text="",
        )

        result = await extract_agendas(state)

        assert result.get("generate_pr_agendas") == []
        assert result.get("generate_pr_summary") == ""

    @pytest.mark.asyncio
    async def test_extract_agendas_success(self):
        """정상적인 추출"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text="[2026-01-20 10:00:00] [김민준] API 설계를 논의하겠습니다.",
        )

        mock_output = ExtractionOutput(
            summary="API 설계 논의",
            agendas=[
                AgendaData(
                    topic="API 설계",
                    description="RESTful API 설계 방향 논의",
                    decisions=[
                        DecisionData(
                            content="RESTful 원칙 준수",
                            context="일관성 유지",
                        )
                    ],
                )
            ],
        )

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.llm"
        ) as mock_llm:
            # chain.invoke 결과 mock
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_output
            mock_llm.__or__ = MagicMock(return_value=mock_chain)

            # prompt | llm | parser 체인 mock
            with patch(
                "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
            ) as mock_prompt_class:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(
                    return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
                )
                mock_prompt_class.from_template.return_value = mock_prompt

                result = await extract_agendas(state)

        assert result.get("generate_pr_summary") == "API 설계 논의"
        agendas = result.get("generate_pr_agendas", [])
        assert len(agendas) == 1
        assert agendas[0]["topic"] == "API 설계"
        assert len(agendas[0]["decisions"]) == 1

    @pytest.mark.asyncio
    async def test_extract_agendas_llm_error(self):
        """LLM 에러 처리"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text="테스트 트랜스크립트",
        )

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
        ) as mock_prompt_class:
            mock_prompt = MagicMock()
            mock_chain = MagicMock()
            mock_chain.invoke.side_effect = Exception("LLM Error")
            mock_prompt.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )
            mock_prompt_class.from_template.return_value = mock_prompt

            result = await extract_agendas(state)

        # 에러 시 빈 결과 반환
        assert result.get("generate_pr_agendas") == []
        assert result.get("generate_pr_summary") == ""

    @pytest.mark.asyncio
    async def test_extract_agendas_truncates_long_transcript(self):
        """긴 트랜스크립트 truncate 처리"""
        # 10000자 이상의 긴 트랜스크립트
        long_transcript = "A" * 10000

        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text=long_transcript,
        )

        mock_output = ExtractionOutput(
            summary="긴 회의 요약",
            agendas=[],
        )

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
        ) as mock_prompt_class:
            mock_prompt = MagicMock()
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_output
            mock_prompt.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )
            mock_prompt_class.from_template.return_value = mock_prompt

            result = await extract_agendas(state)

        # truncate되어도 정상 동작
        assert result.get("generate_pr_summary") == "긴 회의 요약"


class TestExtractionModels:
    """Pydantic 모델 테스트"""

    def test_decision_data_defaults(self):
        """DecisionData 기본값"""
        decision = DecisionData(content="결정 내용")
        assert decision.content == "결정 내용"
        assert decision.context == ""

    def test_agenda_data_defaults(self):
        """AgendaData 기본값"""
        agenda = AgendaData(topic="아젠다")
        assert agenda.topic == "아젠다"
        assert agenda.description == ""
        assert agenda.decisions == []

    def test_extraction_output(self):
        """ExtractionOutput 구조"""
        output = ExtractionOutput(
            summary="요약",
            agendas=[
                AgendaData(
                    topic="주제",
                    decisions=[DecisionData(content="결정")],
                )
            ],
        )
        assert output.summary == "요약"
        assert len(output.agendas) == 1
        assert len(output.agendas[0].decisions) == 1
