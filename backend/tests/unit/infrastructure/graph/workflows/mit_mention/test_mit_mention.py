"""mit_mention 워크플로우 테스트

테스트 범위:
1. gather_context 노드 단위 테스트
2. generate_response 노드 단위 테스트
3. validate_response 노드 단위 테스트
4. route_validation 라우팅 테스트
5. 워크플로우 통합 테스트
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.graph.config import MAX_RETRY
from app.infrastructure.graph.workflows.mit_mention.nodes.context import gather_context
from app.infrastructure.graph.workflows.mit_mention.nodes.generation import generate_response
from app.infrastructure.graph.workflows.mit_mention.nodes.validation import (
    route_validation,
    validate_response,
)
from app.infrastructure.graph.workflows.mit_mention.state import MitMentionState


class TestGatherContext:
    """gather_context 노드 단위 테스트"""

    @pytest.mark.asyncio
    async def test_gather_context_success(self):
        """정상적인 컨텍스트 수집"""
        state = MitMentionState(
            mit_mention_decision_content="API 설계 원칙을 논의했습니다.",
            mit_mention_decision_context="RESTful API 표준을 따르기로 결정",
            mit_mention_thread_history=[
                {"role": "user", "content": "질문1"},
                {"role": "assistant", "content": "답변1"},
                {"role": "user", "content": "질문2"},
            ],
        )

        result = await gather_context(state)

        gathered = result["mit_mention_gathered_context"]
        assert "decision_summary" in gathered
        assert gathered["decision_summary"] == "API 설계 원칙을 논의했습니다."[:500]
        assert gathered["decision_context"] == "RESTful API 표준을 따르기로 결정"[:300]
        assert len(gathered["conversation_history"]) == 3

    @pytest.mark.asyncio
    async def test_gather_context_empty_input(self):
        """빈 입력 처리"""
        state = MitMentionState()

        result = await gather_context(state)

        gathered = result["mit_mention_gathered_context"]
        assert gathered["decision_summary"] == ""
        assert gathered["decision_context"] is None
        assert gathered["conversation_history"] == []

    @pytest.mark.asyncio
    async def test_gather_context_truncates_long_decision(self):
        """긴 결정사항 요약 (500자 제한)"""
        long_content = "A" * 1000

        state = MitMentionState(
            mit_mention_decision_content=long_content,
        )

        result = await gather_context(state)

        gathered = result["mit_mention_gathered_context"]
        assert len(gathered["decision_summary"]) == 500

    @pytest.mark.asyncio
    async def test_gather_context_truncates_long_context(self):
        """긴 맥락 요약 (300자 제한)"""
        long_context = "B" * 500

        state = MitMentionState(
            mit_mention_decision_content="결정",
            mit_mention_decision_context=long_context,
        )

        result = await gather_context(state)

        gathered = result["mit_mention_gathered_context"]
        assert len(gathered["decision_context"]) == 300

    @pytest.mark.asyncio
    async def test_gather_context_limits_thread_history(self):
        """대화 이력 최근 5개만 수집"""
        history = [{"role": "user", "content": f"질문{i}"} for i in range(10)]

        state = MitMentionState(
            mit_mention_decision_content="결정",
            mit_mention_thread_history=history,
        )

        result = await gather_context(state)

        gathered = result["mit_mention_gathered_context"]
        assert len(gathered["conversation_history"]) == 5
        # 최근 5개 확인
        assert gathered["conversation_history"][0]["content"] == "질문5"
        assert gathered["conversation_history"][4]["content"] == "질문9"

    @pytest.mark.asyncio
    async def test_gather_context_handles_malformed_history(self):
        """잘못된 형식의 대화 이력 처리"""
        malformed_history = [
            {},  # role, content 없음
            {"role": "user"},  # content 없음
            {"content": "답변"},  # role 없음
        ]

        state = MitMentionState(
            mit_mention_decision_content="결정",
            mit_mention_thread_history=malformed_history,
        )

        result = await gather_context(state)

        gathered = result["mit_mention_gathered_context"]
        assert len(gathered["conversation_history"]) == 3
        assert gathered["conversation_history"][0]["role"] == "user"
        assert gathered["conversation_history"][0]["content"] == ""


class TestGenerateResponse:
    """generate_response 노드 단위 테스트"""

    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """정상 응답 생성"""
        state = MitMentionState(
            mit_mention_content="API 버전 관리는 어떻게 하나요?",
            mit_mention_gathered_context={
                "decision_summary": "API 설계 원칙 논의",
                "decision_context": "RESTful 원칙 준수",
                "conversation_history": [],
            },
            mit_mention_retry_count=0,
        )

        mock_llm_result = MagicMock()
        mock_llm_result.content = "API 버전은 URL 경로에 포함시키기로 결정했습니다."

        with patch(
            "app.infrastructure.graph.workflows.mit_mention.nodes.generation.get_mention_generator_llm"
        ) as mock_get_llm:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            # chain.ainvoke mock
            with patch(
                "app.infrastructure.graph.workflows.mit_mention.nodes.generation.MENTION_RESPONSE_PROMPT"
            ) as mock_prompt:
                mock_chain = AsyncMock()
                mock_chain.ainvoke.return_value = mock_llm_result
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)

                result = await generate_response(state)

        assert "mit_mention_raw_response" in result
        assert result["mit_mention_raw_response"] == "API 버전은 URL 경로에 포함시키기로 결정했습니다."

    @pytest.mark.asyncio
    async def test_generate_response_with_retry_reason(self):
        """재시도 사유 포함 시 동작"""
        state = MitMentionState(
            mit_mention_content="추가 질문",
            mit_mention_gathered_context={
                "decision_summary": "결정사항",
                "decision_context": None,
                "conversation_history": [],
            },
            mit_mention_retry_count=1,
            mit_mention_retry_reason="응답이 너무 짧습니다",
        )

        mock_llm_result = MagicMock()
        mock_llm_result.content = "더 자세한 답변입니다."

        with patch(
            "app.infrastructure.graph.workflows.mit_mention.nodes.generation.get_mention_generator_llm"
        ) as mock_get_llm:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            with patch(
                "app.infrastructure.graph.workflows.mit_mention.nodes.generation.MENTION_RESPONSE_PROMPT"
            ) as mock_prompt:
                mock_chain = AsyncMock()
                mock_chain.ainvoke.return_value = mock_llm_result
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)

                result = await generate_response(state)

        assert result["mit_mention_raw_response"] == "더 자세한 답변입니다."

    @pytest.mark.asyncio
    async def test_generate_response_llm_error_fallback(self):
        """LLM 에러 시 fallback 응답"""
        state = MitMentionState(
            mit_mention_content="질문",
            mit_mention_gathered_context={
                "decision_summary": "결정",
                "decision_context": None,
                "conversation_history": [],
            },
        )

        with patch(
            "app.infrastructure.graph.workflows.mit_mention.nodes.generation.get_mention_generator_llm"
        ) as mock_get_llm:
            mock_get_llm.side_effect = Exception("LLM API Error")

            result = await generate_response(state)

        assert "mit_mention_raw_response" in result
        assert "죄송합니다" in result["mit_mention_raw_response"]
        assert "오류" in result["mit_mention_raw_response"]

    @pytest.mark.asyncio
    async def test_generate_response_with_conversation_history(self):
        """대화 이력 포함 시 동작"""
        state = MitMentionState(
            mit_mention_content="이어서 질문",
            mit_mention_gathered_context={
                "decision_summary": "결정",
                "decision_context": None,
                "conversation_history": [
                    {"role": "user", "content": "이전 질문" * 50},  # 긴 내용
                    {"role": "assistant", "content": "이전 답변"},
                ],
            },
        )

        mock_llm_result = MagicMock()
        mock_llm_result.content = "맥락을 고려한 답변"

        with patch(
            "app.infrastructure.graph.workflows.mit_mention.nodes.generation.get_mention_generator_llm"
        ) as mock_get_llm:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            with patch(
                "app.infrastructure.graph.workflows.mit_mention.nodes.generation.MENTION_RESPONSE_PROMPT"
            ) as mock_prompt:
                mock_chain = AsyncMock()
                mock_chain.ainvoke.return_value = mock_llm_result
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)

                result = await generate_response(state)

        assert result["mit_mention_raw_response"] == "맥락을 고려한 답변"


class TestValidateResponse:
    """validate_response 노드 단위 테스트"""

    @pytest.mark.asyncio
    async def test_validate_response_pass(self):
        """정상 응답 검증 통과"""
        state = MitMentionState(
            mit_mention_raw_response="적절한 길이의 한국어 답변입니다.",
            mit_mention_retry_count=0,
        )

        result = await validate_response(state)

        assert result["mit_mention_validation"]["passed"] is True
        assert result["mit_mention_response"] == "적절한 길이의 한국어 답변입니다."
        assert result["mit_mention_retry_count"] == 0

    @pytest.mark.asyncio
    async def test_validate_response_too_short(self):
        """응답이 너무 짧음 (10자 미만)"""
        state = MitMentionState(
            mit_mention_raw_response="짧음",
            mit_mention_retry_count=0,
        )

        result = await validate_response(state)

        assert result["mit_mention_validation"]["passed"] is False
        assert "응답이 너무 짧습니다" in result["mit_mention_validation"]["issues"]
        assert result["mit_mention_retry_count"] == 1
        assert result["mit_mention_retry_reason"] == "응답이 너무 짧습니다"

    @pytest.mark.asyncio
    async def test_validate_response_too_long(self):
        """응답이 너무 김 (2000자 초과)"""
        state = MitMentionState(
            mit_mention_raw_response="A" * 2001,
            mit_mention_retry_count=0,
        )

        result = await validate_response(state)

        assert result["mit_mention_validation"]["passed"] is False
        assert "응답이 너무 깁니다" in result["mit_mention_validation"]["issues"]
        assert result["mit_mention_retry_count"] == 1

    @pytest.mark.asyncio
    async def test_validate_response_empty(self):
        """빈 응답"""
        state = MitMentionState(
            mit_mention_raw_response="   ",
            mit_mention_retry_count=0,
        )

        result = await validate_response(state)

        assert result["mit_mention_validation"]["passed"] is False
        assert "빈 응답입니다" in result["mit_mention_validation"]["issues"]

    @pytest.mark.asyncio
    async def test_validate_response_error_message_passes(self):
        """에러 메시지는 검증 통과 (재시도 무의미)"""
        state = MitMentionState(
            mit_mention_raw_response="죄송합니다, 응답을 생성하는 중 오류가 발생했습니다.",
            mit_mention_retry_count=0,
        )

        result = await validate_response(state)

        # 에러 메시지이지만 통과
        assert result["mit_mention_validation"]["passed"] is True
        assert result["mit_mention_response"] == "죄송합니다, 응답을 생성하는 중 오류가 발생했습니다."

    @pytest.mark.asyncio
    async def test_validate_response_max_retry_exceeded(self):
        """최대 재시도 초과 시 강제 통과"""
        state = MitMentionState(
            mit_mention_raw_response="짧음",  # 검증 실패할 내용
            mit_mention_retry_count=MAX_RETRY,  # 이미 최대 재시도
        )

        result = await validate_response(state)

        # 검증 실패했지만 강제 통과
        assert result["mit_mention_validation"]["passed"] is True
        assert result["mit_mention_validation"].get("forced") is True
        assert result["mit_mention_response"] == "짧음"
        assert result["mit_mention_retry_count"] == MAX_RETRY + 1

    @pytest.mark.asyncio
    async def test_validate_response_multiple_issues(self):
        """여러 검증 실패 이슈"""
        state = MitMentionState(
            mit_mention_raw_response="",  # 빈 응답
            mit_mention_retry_count=0,
        )

        result = await validate_response(state)

        issues = result["mit_mention_validation"]["issues"]
        assert len(issues) >= 1
        assert result["mit_mention_retry_reason"] is not None


class TestRouteValidation:
    """route_validation 라우팅 테스트"""

    def test_route_validation_pass(self):
        """검증 통과 시 end로 라우팅"""
        state = MitMentionState(
            mit_mention_validation={"passed": True, "issues": []},
        )

        route = route_validation(state)

        assert route == "end"

    def test_route_validation_fail(self):
        """검증 실패 시 generator로 라우팅"""
        state = MitMentionState(
            mit_mention_validation={"passed": False, "issues": ["응답이 너무 짧습니다"]},
        )

        route = route_validation(state)

        assert route == "generator"

    def test_route_validation_no_validation(self):
        """validation 없을 시 generator로 라우팅 (재생성)"""
        state = MitMentionState()

        route = route_validation(state)

        assert route == "generator"

    def test_route_validation_forced_pass(self):
        """강제 통과 시 end로 라우팅"""
        state = MitMentionState(
            mit_mention_validation={"passed": True, "issues": [], "forced": True},
        )

        route = route_validation(state)

        assert route == "end"


class TestWorkflowIntegration:
    """워크플로우 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_workflow_success(self):
        """전체 워크플로우 정상 실행"""
        from app.infrastructure.graph.workflows.mit_mention.graph import get_graph

        initial_state = MitMentionState(
            mit_mention_comment_id="comment-123",
            mit_mention_content="API 인증은 어떻게 처리하나요?",
            mit_mention_decision_id="decision-456",
            mit_mention_decision_content="OAuth 2.0을 사용하기로 결정했습니다.",
            mit_mention_decision_context="보안과 편의성을 고려",
            mit_mention_thread_history=[],
            mit_mention_retry_count=0,
        )

        mock_llm_result = MagicMock()
        mock_llm_result.content = "OAuth 2.0의 Authorization Code Flow를 사용합니다."

        with patch(
            "app.infrastructure.graph.workflows.mit_mention.nodes.generation.get_mention_generator_llm"
        ) as mock_get_llm:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            with patch(
                "app.infrastructure.graph.workflows.mit_mention.nodes.generation.MENTION_RESPONSE_PROMPT"
            ) as mock_prompt:
                mock_chain = AsyncMock()
                mock_chain.ainvoke.return_value = mock_llm_result
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)

                graph = get_graph()
                result = await graph.ainvoke(initial_state)

        # 최종 상태 검증
        assert "mit_mention_response" in result
        assert result["mit_mention_response"] == "OAuth 2.0의 Authorization Code Flow를 사용합니다."
        assert result["mit_mention_validation"]["passed"] is True

    @pytest.mark.asyncio
    async def test_workflow_retry_logic(self):
        """재시도 로직 동작 확인"""
        from app.infrastructure.graph.workflows.mit_mention.graph import get_graph

        initial_state = MitMentionState(
            mit_mention_comment_id="comment-123",
            mit_mention_content="질문",
            mit_mention_decision_id="decision-456",
            mit_mention_decision_content="결정사항",
            mit_mention_retry_count=0,
        )

        call_count = 0

        async def mock_ainvoke_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # 첫 번째 호출: 너무 짧은 응답
                result = MagicMock()
                result.content = "짧음"
                return result
            else:
                # 두 번째 호출: 정상 응답
                result = MagicMock()
                result.content = "충분히 긴 적절한 응답입니다."
                return result

        with patch(
            "app.infrastructure.graph.workflows.mit_mention.nodes.generation.get_mention_generator_llm"
        ) as mock_get_llm:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            with patch(
                "app.infrastructure.graph.workflows.mit_mention.nodes.generation.MENTION_RESPONSE_PROMPT"
            ) as mock_prompt:
                mock_chain = AsyncMock()
                mock_chain.ainvoke.side_effect = mock_ainvoke_side_effect
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)

                graph = get_graph()
                result = await graph.ainvoke(initial_state)

        # 재시도 확인
        assert call_count == 2  # 2번 호출됨
        assert result["mit_mention_response"] == "충분히 긴 적절한 응답입니다."
        assert result["mit_mention_retry_count"] > 0

    @pytest.mark.asyncio
    async def test_workflow_max_retry_exceeded(self):
        """최대 재시도 초과 시 강제 종료"""
        from app.infrastructure.graph.workflows.mit_mention.graph import get_graph

        initial_state = MitMentionState(
            mit_mention_comment_id="comment-123",
            mit_mention_content="질문",
            mit_mention_decision_id="decision-456",
            mit_mention_decision_content="결정사항",
            mit_mention_retry_count=0,
        )

        # 항상 짧은 응답 (검증 실패)
        mock_llm_result = MagicMock()
        mock_llm_result.content = "짧음"

        with patch(
            "app.infrastructure.graph.workflows.mit_mention.nodes.generation.get_mention_generator_llm"
        ) as mock_get_llm:
            mock_llm = AsyncMock()
            mock_get_llm.return_value = mock_llm

            with patch(
                "app.infrastructure.graph.workflows.mit_mention.nodes.generation.MENTION_RESPONSE_PROMPT"
            ) as mock_prompt:
                mock_chain = AsyncMock()
                mock_chain.ainvoke.return_value = mock_llm_result
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)

                graph = get_graph()
                result = await graph.ainvoke(initial_state)

        # 최대 재시도 후 강제 통과
        assert result["mit_mention_retry_count"] > MAX_RETRY
        assert result["mit_mention_validation"]["passed"] is True
        assert result["mit_mention_validation"].get("forced") is True
