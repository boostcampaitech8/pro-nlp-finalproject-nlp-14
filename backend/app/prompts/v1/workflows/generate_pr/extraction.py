"""Agenda/Decision 추출 프롬프트

Version: 1.0.0
Description: 회의록에서 Agenda와 Decision을 추출하는 프롬프트
Changelog:
    1.0.0: 초기 버전 (workflows/extraction.py에서 분리)
"""

VERSION = "1.0.0"

# =============================================================================
# Agenda/Decision 추출 프롬프트
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
                "context": "결정 맥락/근거",
            },  # 또는 null
        }
    ],
}
