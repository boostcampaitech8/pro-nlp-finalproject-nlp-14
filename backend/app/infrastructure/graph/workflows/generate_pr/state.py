"""generate_pr State 정의

워크플로우 실행 중 공유되는 상태
"""

from typing import Annotated, TypedDict


class GeneratePrState(TypedDict, total=False):
    """generate_pr 서브그래프 State

    State 필드 prefix 규칙: 서브그래프 전용 필드는 generate_pr_ prefix 사용
    """

    # 입력 필드
    generate_pr_meeting_id: Annotated[str, "회의 ID"]
    generate_pr_transcript_text: Annotated[str, "트랜스크립트 전문"]

    # 중간 상태 필드 (LLM 추출 결과)
    generate_pr_agendas: Annotated[list[dict], "추출된 Agenda+Decision 데이터"]
    # [{
    #     "topic": "아젠다 주제",
    #     "description": "설명",
    #     "decisions": [{"content": "결정 내용", "context": "맥락"}]
    # }]
    generate_pr_summary: Annotated[str, "회의 요약"]

    # 출력 필드
    generate_pr_agenda_ids: Annotated[list[str], "생성된 Agenda IDs"]
    generate_pr_decision_ids: Annotated[list[str], "생성된 Decision IDs"]
