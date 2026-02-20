"""extract_agendas 노드 테스트 — 2단계 파이프라인"""

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.graph.workflows.generate_pr.nodes.extraction import (
    AgendaData,
    AgendaKeywords,
    DecisionData,
    DecisionKeywords,
    ExtractionOutput,
    KeywordExtractionOutput,
    MinutesAgendaData,
    MinutesDecisionData,
    MinutesGenerationOutput,
    SpanRef,
    _format_keywords_for_minutes_prompt,
    _format_utterances_for_prompt,
    _format_realtime_topics_for_prompt,
    _keywords_overlap_ratio,
    _merge_keyword_groups,
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


# Step 1 mock 출력 (키워드 추출)
def _make_keyword_output() -> KeywordExtractionOutput:
    return KeywordExtractionOutput(
        agendas=[
            AgendaKeywords(
                evidence_spans=[
                    SpanRef(start_utt_id="utt-1", end_utt_id="utt-1"),
                ],
                topic_keywords=["API", "설계", "RESTful"],
                decision=DecisionKeywords(
                    who=None,
                    what="RESTful 원칙 준수",
                    when=None,
                    verb="적용하기로 결정",
                    evidence_spans=[
                        SpanRef(start_utt_id="utt-1", end_utt_id="utt-1"),
                    ],
                ),
            )
        ]
    )


# Step 2 mock 출력 (회의록 생성)
def _make_minutes_output() -> MinutesGenerationOutput:
    return MinutesGenerationOutput(
        summary="API 설계 논의",
        agendas=[
            MinutesAgendaData(
                topic="RESTful API 설계 방향 결정",
                description="API 설계 시 RESTful 원칙을 적용하는 방향을 논의",
                decision=MinutesDecisionData(
                    content="RESTful 원칙을 적용하기로 결정",
                    context="일관성 유지를 위해",
                ),
            )
        ],
    )


class TestExtractAgendas:
    """extract_agendas 노드 테스트 (2단계 파이프라인)"""

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
        """정상적인 2단계 추출 + 실시간 토픽 프롬프트 주입 확인"""
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

        # Step 1 mock
        mock_keyword_chain = MagicMock()
        mock_keyword_chain.invoke.return_value = _make_keyword_output()

        # Step 2 mock
        mock_minutes_chain = MagicMock()
        mock_minutes_chain.invoke.return_value = _make_minutes_output()

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.get_keyword_extractor_llm",
            return_value=MagicMock(),
        ), patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.get_minutes_generator_llm",
            return_value=MagicMock(),
        ), patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
        ) as mock_prompt_class:
            # 첫 호출은 Step 1 chain, 두 번째 호출은 Step 2 chain
            mock_prompt_class.from_template.side_effect = [
                _mock_chain_pipeline(mock_keyword_chain),
                _mock_chain_pipeline(mock_minutes_chain),
            ]
            result = await extract_agendas(state)

        assert result.get("generate_pr_summary") == "API 설계 논의"
        agendas = result.get("generate_pr_agendas", [])
        assert len(agendas) == 1
        assert agendas[0]["topic"] == "RESTful API 설계 방향 결정"
        assert agendas[0]["decision"]["content"] == "RESTful 원칙을 적용하기로 결정"
        # evidence는 Step 1에서 가져옴
        assert len(agendas[0]["evidence"]) >= 1

        # Step 1에 realtime_topics가 전달되었는지 확인
        step1_payload = mock_keyword_chain.invoke.call_args.args[0]
        assert "API 설계" in step1_payload["realtime_topics"]

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
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.get_keyword_extractor_llm",
            return_value=MagicMock(),
        ), patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
        ) as mock_prompt_class:
            mock_prompt_class.from_template.return_value = _mock_chain_pipeline(mock_chain)
            result = await extract_agendas(state)

        assert result.get("generate_pr_agendas") == []
        assert result.get("generate_pr_summary") == ""

    @pytest.mark.asyncio
    async def test_extract_agendas_no_evidence_filtered(self):
        """evidence 없는 키워드 그룹은 필터링"""
        state = GeneratePrState(
            generate_pr_meeting_id="meeting-1",
            generate_pr_transcript_text="테스트 트랜스크립트",
        )

        # Step 1: evidence가 없는 agenda
        keyword_output = KeywordExtractionOutput(
            agendas=[
                AgendaKeywords(
                    evidence_spans=[],  # 빈 evidence
                    topic_keywords=["키워드"],
                    decision=None,
                )
            ]
        )
        mock_keyword_chain = MagicMock()
        mock_keyword_chain.invoke.return_value = keyword_output

        with patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.get_keyword_extractor_llm",
            return_value=MagicMock(),
        ), patch(
            "app.infrastructure.graph.workflows.generate_pr.nodes.extraction.ChatPromptTemplate"
        ) as mock_prompt_class:
            mock_prompt_class.from_template.return_value = _mock_chain_pipeline(mock_keyword_chain)
            result = await extract_agendas(state)

        # evidence 없으면 Step 2 호출 없이 빈 결과
        assert result.get("generate_pr_agendas") == []


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
        assert decision.evidence == []

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
                    evidence=[
                        SpanRef(start_utt_id="utt-1", end_utt_id="utt-1"),
                    ],
                    decision=DecisionData(
                        content="결정",
                        evidence=[
                            SpanRef(start_utt_id="utt-1", end_utt_id="utt-1"),
                        ],
                    ),
                )
            ],
        )
        assert output.summary == "요약"
        assert len(output.agendas) == 1
        assert output.agendas[0].decision is not None

    def test_keyword_extraction_output(self):
        output = KeywordExtractionOutput(
            agendas=[
                AgendaKeywords(
                    evidence_spans=[SpanRef(start_utt_id="utt-1", end_utt_id="utt-3")],
                    topic_keywords=["Redis", "캐시", "도입"],
                    decision=DecisionKeywords(
                        who="김민준",
                        what="Redis 캐시 도입",
                        when="다음 주",
                        verb="검토하기로 결정",
                        evidence_spans=[SpanRef(start_utt_id="utt-2", end_utt_id="utt-3")],
                    ),
                )
            ]
        )
        assert len(output.agendas) == 1
        assert output.agendas[0].topic_keywords == ["Redis", "캐시", "도입"]
        assert output.agendas[0].decision.who == "김민준"
        assert output.agendas[0].decision.what == "Redis 캐시 도입"

    def test_minutes_generation_output(self):
        output = MinutesGenerationOutput(
            summary="회의 요약",
            agendas=[
                MinutesAgendaData(
                    topic="Redis 캐시 도입 검토",
                    description="캐시 전략을 비교 검토함",
                    decision=MinutesDecisionData(
                        content="김민준이 Redis 캐시 도입 방안을 다음 주까지 검토하기로 결정",
                        context="API 응답 속도 개선 필요",
                    ),
                )
            ],
        )
        assert output.summary == "회의 요약"
        assert len(output.agendas) == 1
        assert output.agendas[0].decision.content.startswith("김민준이")


class TestKeywordMerging:
    """키워드 병합 테스트"""

    def test_keywords_overlap_ratio(self):
        assert _keywords_overlap_ratio(["A", "B", "C"], ["A", "B", "C"]) == 1.0
        assert _keywords_overlap_ratio(["A", "B"], ["C", "D"]) == 0.0
        assert _keywords_overlap_ratio([], []) == 0.0

    def test_keywords_overlap_ratio_partial(self):
        ratio = _keywords_overlap_ratio(["A", "B", "C"], ["B", "C", "D"])
        # intersection=2(B,C), union=4(A,B,C,D) => 0.5
        assert ratio == pytest.approx(0.5)

    def test_merge_keyword_groups_no_overlap(self):
        chunks = [
            [
                {"topic_keywords": ["A", "B"], "evidence_spans": [{"start_utt_id": "utt-1", "end_utt_id": "utt-2"}], "decision": None},
            ],
            [
                {"topic_keywords": ["C", "D"], "evidence_spans": [{"start_utt_id": "utt-5", "end_utt_id": "utt-6"}], "decision": None},
            ],
        ]
        merged = _merge_keyword_groups(chunks)
        assert len(merged) == 2

    def test_merge_keyword_groups_with_overlap(self):
        chunks = [
            [
                {"topic_keywords": ["Redis", "캐시", "도입"], "evidence_spans": [{"start_utt_id": "utt-1", "end_utt_id": "utt-3"}], "decision": None},
            ],
            [
                {"topic_keywords": ["Redis", "캐시", "적용"], "evidence_spans": [{"start_utt_id": "utt-2", "end_utt_id": "utt-4"}], "decision": None},
            ],
        ]
        merged = _merge_keyword_groups(chunks)
        # Redis, 캐시가 겹침 — overlap >= 0.4이므로 병합
        assert len(merged) == 1
        assert "도입" in merged[0]["topic_keywords"]
        assert "적용" in merged[0]["topic_keywords"]
        assert len(merged[0]["evidence_spans"]) == 2  # 중복 제거

    def test_merge_keyword_groups_decision_inheritance(self):
        """첫 청크에 decision 없고 두 번째 청크에 있으면 병합 시 추가"""
        chunks = [
            [
                {"topic_keywords": ["배포", "일정"], "evidence_spans": [{"start_utt_id": "utt-1", "end_utt_id": "utt-2"}], "decision": None},
            ],
            [
                {"topic_keywords": ["배포", "일정", "확정"], "evidence_spans": [{"start_utt_id": "utt-3", "end_utt_id": "utt-4"}],
                 "decision": {"who": None, "what": "3월 배포", "when": "3월 31일", "verb": "확정", "evidence_spans": [{"start_utt_id": "utt-3", "end_utt_id": "utt-4"}]}},
            ],
        ]
        merged = _merge_keyword_groups(chunks)
        assert len(merged) == 1
        assert merged[0]["decision"] is not None
        assert merged[0]["decision"]["what"] == "3월 배포"
