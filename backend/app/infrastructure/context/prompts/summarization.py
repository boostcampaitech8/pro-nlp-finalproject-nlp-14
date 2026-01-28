"""L1 요약 프롬프트

토픽별 요약 생성을 위한 프롬프트
"""

L1_SUMMARY_PROMPT = """
회의 토픽을 요약하세요.

## 토픽 제목
{topic_name}

## 해당 토픽의 발화 내용
{topic_utterances}

## 요약 형식 (JSON)
{{
    "summary": "3-5문장 요약",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...],
    "decisions": ["결정된 사항 (있다면)"],
    "pending": ["보류/미해결 사항 (있다면)"],
    "participants": ["발언한 참여자 목록"],
    "keywords": ["핵심 키워드"]
}}
"""

# 요약 응답 파싱용 스키마
L1_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "pending": {"type": "array", "items": {"type": "string"}},
        "participants": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary"],
}


# 재귀적 요약 프롬프트 (토픽 내 25턴 초과 시 사용)
RECURSIVE_SUMMARY_PROMPT = """
기존 요약과 새로운 발화를 통합하여 하나의 요약을 생성하세요.

## 기존 요약
{previous_summary}

## 새로운 발화 (Turn {start_turn}~{end_turn})
{new_utterances}

## 지침
1. 기존 요약의 핵심 내용을 유지하면서 새 정보를 통합
2. 중복 제거 및 정보 압축
3. 시간 순서대로 주요 논의 흐름 유지
4. 토큰 예산: 최대 500 토큰

## 출력 형식 (JSON만 출력)
{{
    "summary": "통합된 3-5문장 요약",
    "key_points": ["핵심 포인트 (최대 5개)"],
    "keywords": ["키워드 (최대 10개)"]
}}
"""

# 재귀적 요약 응답 파싱용 스키마
RECURSIVE_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
    },
    "required": ["summary"],
}
