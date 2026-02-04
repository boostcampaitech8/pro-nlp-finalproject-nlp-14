"""Evaluation 프롬프트 - 도구 실행 결과 평가용

Version: 2.0.0
Description: 도구 실행 결과를 평가하고 다음 단계(success/retry/replanning)를 결정하는 프롬프트
Changelog:
    1.0.0: 초기 버전 (orchestration/nodes/evaluation.py에서 분리)
    2.0.0: 동적 도구 설명 주입 지원, 빌더 함수 추가
"""
VERSION = "2.0.0"


# =============================================================================
# 평가 프롬프트
# =============================================================================

EVALUATION_PROMPT = """당신은 도구 실행 결과를 평가하는 평가자입니다.
반드시 JSON 형식으로만 응답해야 합니다.

=== 평가 대상 ===
사용자 질문: {query}
원래 계획: {plan}

=== 사용된 도구 ===
도구 이름: {tool_name}
도구 설명: {tool_description}
주요 기능: {tool_can_do}
제한 사항: {tool_cannot_do}

=== 도구 실행 결과 ===
{tool_results}

=== 현재 상태 ===
재시도 횟수: {retry_count}

=== 평가 기준 ===
도구 실행 결과를 평가하고 다음 단계를 결정하세요:

1. **success**: 도구 실행 결과가 충분하고 사용자 질문에 답변 가능
   - 사용자가 원하는 정보가 결과에 포함되어 있는가?
   - 추가 정보 없이 답변을 생성할 수 있는가?

2. **retry**: 도구 실행 실패 또는 결과 불충분 (같은 도구 재실행)
   - 일시적 오류로 재시도하면 성공할 가능성이 있는가?
   - 쿼리를 수정하면 더 나은 결과를 얻을 수 있는가?

3. **replanning**: 계획 자체가 잘못됨 (다른 접근 방법 필요)
   - 선택한 도구가 질문과 맞지 않는가?
   - 다른 도구를 사용해야 하는가?
   - 질문 자체가 답변 불가능한가?

=== 판단 질문 ===
- 사용자 질문에 대해 답하기에 충분한 정보를 가졌는가?
- 사용자 질문에 답변하기 위해 올바른 계획을 세웠는가?
- 계획과 실행 결과가 일치하는가?
- 추가 정보나 다른 도구가 필요한가?

중요: 다른 텍스트 없이 오직 JSON만 출력하세요!

{format_instructions}

예시:
{{"evaluation": "검색 결과 충분", "status": "success", "reason": "질문에 답변 가능"}}"""


# =============================================================================
# 평가 결과 스키마
# =============================================================================

EVALUATION_OUTPUT_SCHEMA = {
    "evaluation": "평가 요약 (예: '검색 결과 충분', '계획 재수립 필요')",
    "status": "평가 상태: 'success', 'retry', 'replanning' 중 하나",
    "reason": "평가 이유 및 상세 설명"
}


# =============================================================================
# 상태 상수
# =============================================================================

class EvaluationStatus:
    """평가 상태"""
    SUCCESS = "success"
    RETRY = "retry"
    REPLANNING = "replanning"


# =============================================================================
# 빌더 함수
# =============================================================================

def build_evaluation_prompt(
    query: str,
    plan: str,
    tool_name: str,
    tool_results: str,
    retry_count: int,
    format_instructions: str,
    tool_descriptions: dict | None = None,
) -> str:
    """평가 프롬프트 빌드 - 도구 설명 자동 주입

    Args:
        query: 사용자 질문
        plan: 원래 계획
        tool_name: 사용된 도구 이름
        tool_results: 도구 실행 결과
        retry_count: 현재 재시도 횟수
        format_instructions: 출력 포맷 지시
        tool_descriptions: planning.py의 TOOL_DESCRIPTIONS 딕셔너리 (선택)

    Returns:
        완성된 평가 프롬프트
    """
    # 도구 설명 가져오기
    tool_description = "알 수 없는 도구"
    tool_can_do = "정보 없음"

    if tool_descriptions and tool_name in tool_descriptions:
        tool_info = tool_descriptions[tool_name]
        tool_description = tool_info.get("description", "알 수 없는 도구")
        can_do_list = tool_info.get("can_do", [])
        tool_can_do = ", ".join(can_do_list) if can_do_list else "정보 없음"

    return EVALUATION_PROMPT.format(
        query=query,
        plan=plan,
        tool_name=tool_name,
        tool_description=tool_description,
        tool_can_do=tool_can_do,
        tool_results=tool_results,
        retry_count=retry_count,
        format_instructions=format_instructions,
    )


def get_tool_info(tool_name: str, tool_descriptions: dict) -> dict:
    """도구 정보 반환

    Args:
        tool_name: 도구 이름
        tool_descriptions: planning.py의 TOOL_DESCRIPTIONS 딕셔너리

    Returns:
        도구 정보 딕셔너리 (name, description, can_do, cannot_do)
    """
    default_info = {
        "name": tool_name,
        "description": "알 수 없는 도구",
        "can_do": [],
        "cannot_do": [],
    }

    if tool_descriptions and tool_name in tool_descriptions:
        tool_info = tool_descriptions[tool_name]
        return {
            "name": tool_name,
            "description": tool_info.get("description", "알 수 없는 도구"),
            "can_do": tool_info.get("can_do", []),
            "cannot_do": tool_info.get("cannot_do", []),
        }

    return default_info
