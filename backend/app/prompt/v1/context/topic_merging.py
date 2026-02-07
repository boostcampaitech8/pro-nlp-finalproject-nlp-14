"""Topic Merging Prompts - 유사 토픽 병합용 프롬프트

System/User 프롬프트 분리: 규칙·포맷은 System, 실제 데이터만 User
"""

TOPIC_MERGE_SYSTEM_PROMPT = """두 개의 유사한 토픽을 하나로 통합하세요.

## 지침
1. 두 요약의 핵심 내용을 모두 포함
2. 중복 정보 제거
3. 시간 순서 유지 (가능한 경우)
4. 500 토큰 이내로 통합
5. 결정사항, 액션아이템이 있으면 명시적으로 표기

## 출력 형식 (JSON만 출력)
{{
    "merged_topic_name": "통합된 토픽 이름 (5단어 이내)",
    "merged_summary": "통합된 3-5문장 요약",
    "keywords": ["키워드 (최대 10개)"]
}}"""

TOPIC_MERGE_USER_PROMPT = """## 토픽 1: {topic_name_1}
{summary_1}

## 토픽 2: {topic_name_2}
{summary_2}"""

TOPIC_MERGE_SCHEMA = {
    "type": "object",
    "properties": {
        "merged_topic_name": {"type": "string"},
        "merged_summary": {"type": "string"},
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
        },
    },
    "required": ["merged_topic_name", "merged_summary"],
}


TOPIC_NAME_MERGE_PROMPT = """
두 토픽 이름을 하나의 대표 이름으로 통합하세요.

토픽 1: {name_1}
토픽 2: {name_2}

지침:
- 두 토픽의 공통 주제를 반영
- 5단어 이내의 간결한 이름
- 한국어로 작성

출력: 통합된 토픽 이름만 출력 (따옴표 없이)
"""
