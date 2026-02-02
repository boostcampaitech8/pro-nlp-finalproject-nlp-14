"""Extraction 프롬프트 - 회의록 데이터 추출용

Version: 1.0.0
Description: 회의록에서 Agenda/Decision/Action Item을 추출하는 프롬프트
Changelog:
    1.0.0: 초기 버전 (generate_pr/extraction.py, mit_action/extraction.py에서 분리)
"""

VERSION = "1.0.0"

# =============================================================================
# Agenda/Decision 추출 프롬프트 (generate_pr 워크플로우)
# =============================================================================

AGENDA_EXTRACTION_PROMPT = """당신은 회의록 분석 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.

다음 회의 트랜스크립트를 분석하여 아젠다와 결정사항을 추출하세요.

트랜스크립트:
{transcript}

분석 지침:
1. 회의에서 논의된 주요 주제(아젠다)를 식별하세요
2. 각 아젠다에서 합의된 결정사항을 추출하세요 (한 안건당 최대 1개)
3. 결정사항이 없는 아젠다는 decision을 null로 두세요
4. 전체 회의를 2-3문장으로 요약하세요

중요: 다른 텍스트 없이 오직 JSON만 출력하세요!

{format_instructions}

예시:
{{"summary": "프로젝트 진행 상황과 다음 스프린트 계획을 논의했습니다.", "agendas": [{{"topic": "스프린트 리뷰", "description": "지난 스프린트 결과 검토", "decision": {{"content": "다음 스프린트에서 성능 개선 우선", "context": "사용자 피드백 기반"}}}}]}}"""

# Agenda 추출 결과 스키마 (참고용)
AGENDA_EXTRACTION_SCHEMA = {
    "summary": "회의 전체 요약 (2-3문장)",
    "agendas": [
        {
            "topic": "아젠다 주제",
            "description": "아젠다 설명",
            "decision": {
                "content": "결정 내용",
                "context": "결정 맥락/근거"
            }  # 또는 null
        }
    ]
}

# =============================================================================
# Action Item 추출 프롬프트 (mit_action 워크플로우)
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
            "assignee_name": "담당자 이름 또는 null"
        }
    ]
}

# Action Item 기본 신뢰도
DEFAULT_ACTION_CONFIDENCE = 0.8
