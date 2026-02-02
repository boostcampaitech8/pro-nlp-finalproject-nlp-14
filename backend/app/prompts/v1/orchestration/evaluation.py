"""Evaluation 프롬프트 - 도구 실행 결과 평가용

Version: 1.0.0
Description: 도구 실행 결과를 평가하고 다음 단계(success/retry/replanning)를 결정하는 프롬프트
Changelog:
    1.0.0: 초기 버전 (orchestration/nodes/evaluation.py에서 분리)
"""

VERSION = "1.0.0"

# 도구 실행 결과 평가 프롬프트
EVALUATION_PROMPT = """당신은 도구 실행 결과를 평가하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.

사용자 질문: {query}
원래 계획: {plan}
도구 실행 결과: {tool_results}
현재 재시도 횟수: {retry_count}

도구 실행 결과를 평가하고 다음 단계를 결정하세요:

1. **success**: 도구 실행 결과가 충분하고 사용자 질문에 답변 가능
2. **retry**: 도구 실행 실패 또는 결과 불충분 (같은 도구 재실행)
3. **replanning**: 계획 자체가 잘못됨 (다른 접근 방법 필요)

평가 기준:
- 계획과 실행 결과가 일치하는가?
- 결과가 질문에 답하기에 충분한가?
- 추가 정보나 다른 도구가 필요한가?

중요: 다른 텍스트 없이 오직 JSON만 출력하세요!

{format_instructions}

예시:
{{"evaluation": "결과가 충분함", "status": "success", "reason": "질문에 답변 가능"}}"""

# 평가 결과 스키마 (참고용)
EVALUATION_OUTPUT_SCHEMA = {
    "evaluation": "평가 요약 (예: '검색 결과 충분', '계획 재수립 필요')",
    "status": "평가 상태: 'success', 'retry', 'replanning' 중 하나",
    "reason": "평가 이유 및 상세 설명"
}

# 복합 쿼리 감지 키워드
COMPOSITE_QUERY_KEYWORDS = {
    "assignment": ["맡고 있는", "담당", "책임자", "담당자", "맡은"],
    "team": ["팀원", "같은 팀", "팀에서", "팀의"]
}

# 서브쿼리 감지 키워드
SUBQUERY_KEYWORDS = [
    "이전에 찾은", "그 담당자", "그 사람", "그 액션",
    "그 팀원", "그 팀", "그 결정", "찾은"
]
