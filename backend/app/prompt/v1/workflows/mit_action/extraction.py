"""Action Item 추출 프롬프트

Version: 1.0.0
Description: Decision에서 Action Item을 추출하는 프롬프트
Changelog:
    1.0.0: 초기 버전 (workflows/extraction.py에서 분리)
"""

VERSION = "1.0.0"

# =============================================================================
# Action Item 추출 프롬프트
# =============================================================================

ACTION_EXTRACTION_PROMPT = """당신은 회의 결정사항에서 Action Item을 추출하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.

다음 결정사항에서 실행 가능한 Action Item을 추출하세요.

결정사항:
{decision_content}

맥락:
{decision_context}

추출 지침:
1. 구체적인 할 일만 추출하세요 (모호한 내용 제외)
2. 담당자가 언급되면 assignee_name에 기록하세요
3. 기한이 언급되면 YYYY-MM-DD 형식으로 due_date에 기록하세요
4. Action Item이 없으면 빈 배열을 반환하세요
{retry_instruction}

중요: 다른 텍스트 없이 오직 JSON만 출력하세요!

{format_instructions}

예시:
{{"action_items": [{{"content": "API 문서 작성", "due_date": "2026-02-01", "assignee_name": "김철수"}}]}}"""

# Action 추출 재시도 지침
ACTION_RETRY_INSTRUCTION = """
이전 추출이 거부되었습니다. 사유: {retry_reason}
이 점을 개선하여 다시 추출하세요."""

# Action 추출 결과 스키마 (참고용)
ACTION_EXTRACTION_SCHEMA = {
    "action_items": [
        {
            "content": "할 일 내용 (간결하게)",
            "due_date": "YYYY-MM-DD 형식 또는 null",
            "assignee_name": "담당자 이름 또는 null",
        }
    ]
}

# Action Item 기본 신뢰도
DEFAULT_ACTION_CONFIDENCE = 0.8
