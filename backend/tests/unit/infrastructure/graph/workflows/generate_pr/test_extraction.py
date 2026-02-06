"""extract_agendas 노드 테스트"""

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.graph.workflows.generate_pr.nodes.extraction import (
    AgendaData,
    DecisionData,
    ExtractionOutput,
    _format_utterances_for_prompt,
    _format_realtime_topics_for_prompt,
    _prepare_utterances,
    extract_agendas,
)
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState


def _mock_chain_pipeline(mock_chain: MagicMock):
    """prompt | llm | parser 체인 mock."""
    mock_prompt = MagicMock()
    mock_middle = MagicMock()
    mock_prompt.__or__.return_value = mock_middle
    mock_middle.__or__.return_value = mock_chain
    return mock_prompt


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
        """정상적인 추출 + 실시간 토픽 프롬프트 주입 확인"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text="[2026-01-20 10:00:00] [김민준] API 설계를 논의하겠습니다.",
            generate_pr_realtime_topics=[
                {
                    "name": "API 설계",
                    "summary": "엔드포인트 설계 방향을 논의",
                    "startTurn": 1,
                    "endTurn": 25,
                    "keywords": ["API", "REST"],
                }
            ],
        )

        mock_output = ExtractionOutput(
            summary="API 설계 논의",
            agendas=[
                AgendaData(
                    topic="API 설계",
                    description="RESTful API 설계 방향 논의",
                    decision=DecisionData(
                        content="RESTful 원칙 준수",
                        context="일관성 유지",
                    ),
                )
            ],
        )
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_output

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.get_pr_generator_llm",
            return_value=MagicMock(),
        ):
            with patch(
                "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
            ) as mock_prompt_class:
                mock_prompt_class.from_template.return_value = _mock_chain_pipeline(mock_chain)
                result = await extract_agendas(state)

        assert result.get("generate_pr_summary") == "API 설계 논의"
        agendas = result.get("generate_pr_agendas", [])
        assert len(agendas) == 1
        assert agendas[0]["topic"] == "API 설계"
        assert agendas[0]["decision"]["content"] == "RESTful 원칙 준수"

        called_payload = mock_chain.invoke.call_args.args[0]
        assert "API 설계" in called_payload["realtime_topics"]
        assert "트랜스크립트" not in called_payload["realtime_topics"]

    @pytest.mark.asyncio
    async def test_extract_agendas_llm_error(self):
        """LLM 에러 처리"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text="테스트 트랜스크립트",
        )
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("LLM Error")

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.get_pr_generator_llm",
            return_value=MagicMock(),
        ):
            with patch(
                "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
            ) as mock_prompt_class:
                mock_prompt_class.from_template.return_value = _mock_chain_pipeline(mock_chain)
                result = await extract_agendas(state)

        assert result.get("generate_pr_agendas") == []
        assert result.get("generate_pr_summary") == ""

    @pytest.mark.asyncio
    async def test_extract_agendas_truncates_long_transcript(self):
        """긴 트랜스크립트 truncate 처리"""
        # max_length(100000)보다 긴 트랜스크립트
        long_transcript = "A" * 101000

        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text=long_transcript,
        )

        mock_output = ExtractionOutput(
            summary="긴 회의 요약",
            agendas=[],
        )
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_output

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.get_pr_generator_llm",
            return_value=MagicMock(),
        ):
            with patch(
                "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
            ) as mock_prompt_class:
                mock_prompt_class.from_template.return_value = _mock_chain_pipeline(mock_chain)
                result = await extract_agendas(state)

        assert result.get("generate_pr_summary") == "긴 회의 요약"
        payload = mock_chain.invoke.call_args.args[0]
        assert payload["transcript"].endswith("\n... (truncated)")


class TestRealtimeTopicFormatter:
    """실시간 토픽 프롬프트 포맷팅 테스트"""

    def test_format_realtime_topics_sorted(self):
        topics = [
            {"name": "후반", "summary": "후반 논의", "startTurn": 26, "endTurn": 50, "keywords": []},
            {"name": "초반", "summary": "초반 논의", "startTurn": 1, "endTurn": 25, "keywords": ["시작"]},
        ]

        formatted = _format_realtime_topics_for_prompt(topics)
        first_line = formatted.splitlines()[0]

        assert "초반" in first_line
        assert "키워드: 시작" in formatted

    def test_format_realtime_topics_empty(self):
        assert _format_realtime_topics_for_prompt([]) == "(없음)"


class TestUtteranceFormatting:
    """발화 ID 포맷팅 테스트"""

    def test_prepare_utterances_keeps_original_id_and_sets_llm_turn_id(self):
        state = GeneratePrState(
            generate_pr_transcript_utterances=[
                {
                    "id": "59f18d9a-9a8b-4d76-af01-0ea1ecb1278d",
                    "speaker_name": "김민준",
                    "text": "배포 일정을 확정합시다.",
                    "start_ms": 0,
                    "end_ms": 1200,
                }
            ]
        )

        utterances = _prepare_utterances(state)

        assert utterances[0]["id"] == "59f18d9a-9a8b-4d76-af01-0ea1ecb1278d"
        assert utterances[0]["llm_utt_id"] == "utt-1"

        prompt_text = _format_utterances_for_prompt(utterances)
        assert "[Utt utt-1]" in prompt_text
        assert "59f18d9a-9a8b-4d76-af01-0ea1ecb1278d" not in prompt_text


class TestExtractionModels:
    """Pydantic 모델 테스트"""

    def test_decision_data_defaults(self):
        decision = DecisionData(content="결정 내용")
        assert decision.content == "결정 내용"
        assert decision.context == ""

    def test_agenda_data_defaults(self):
        agenda = AgendaData(topic="아젠다")
        assert agenda.topic == "아젠다"
        assert agenda.description == ""
        assert agenda.decision is None

    def test_extraction_output(self):
        output = ExtractionOutput(
            summary="요약",
            agendas=[
                AgendaData(
                    topic="주제",
                    decision=DecisionData(content="결정"),
                )
            ],
        )
        assert output.summary == "요약"
        assert len(output.agendas) == 1
        assert output.agendas[0].decision is not None
