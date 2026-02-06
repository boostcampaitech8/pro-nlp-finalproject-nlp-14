"""Voice Planning prompt template and builder."""

VOICE_SYSTEM_PROMPT_TEMPLATE = """당신은 MIT 회의 어시스턴트입니다.
현재 진행 중인 회의(id: {meeting_id}) 내에서 질문에 답변합니다.

규칙:
1. 과거 회의 내용, 회의록, 특정 인물/키워드와 관련된 회의는 mit_search 도구 사용
2. 팀/회의 정보 조회 시 해당 Query 도구 사용
3. meeting_id 컨텍스트를 우선 활용하고, 추측 답변은 금지
4. 회의 내용과 관련 없는 질문은 정중히 안내"""


def build_voice_system_prompt(meeting_id: str) -> str:
    """VOICE 모드용 시스템 프롬프트 생성.

    Args:
        meeting_id: 현재 진행 중인 회의 ID

    Returns:
        완성된 시스템 프롬프트 문자열
    """
    return VOICE_SYSTEM_PROMPT_TEMPLATE.format(meeting_id=meeting_id)
