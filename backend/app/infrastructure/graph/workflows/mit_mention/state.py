"""mit_mention State 정의

@mit 멘션에 대한 AI 응답 생성 워크플로우 상태
"""

from typing import Annotated, TypedDict


class MitMentionState(TypedDict, total=False):
    """mit_mention 워크플로우 State

    State 필드 prefix 규칙: 워크플로우 전용 필드는 mit_mention_ prefix 사용
    """

    # 입력 필드
    mit_mention_comment_id: Annotated[str, "원본 Comment ID"]
    mit_mention_content: Annotated[str, "Comment 내용 (멘션 제외)"]
    mit_mention_decision_id: Annotated[str, "Decision ID"]
    mit_mention_decision_content: Annotated[str, "Decision 내용"]
    mit_mention_decision_context: Annotated[str | None, "Decision 맥락"]
    mit_mention_thread_history: Annotated[list[dict] | None, "이전 대화 내역"]
    mit_mention_meeting_id: Annotated[str | None, "Meeting ID"]

    # 컨텍스트 수집 결과
    mit_mention_gathered_context: Annotated[dict | None, "수집된 컨텍스트"]

    # 생성 결과 필드
    mit_mention_raw_response: Annotated[str | None, "LLM 생성 응답 (raw)"]

    # 검증 결과 필드
    mit_mention_validation: Annotated[dict | None, "응답 검증 결과"]

    # 재시도 관련 필드
    mit_mention_retry_count: Annotated[int, "재시도 횟수"]
    mit_mention_retry_reason: Annotated[str | None, "검증 실패 사유"]

    # 출력 필드
    mit_mention_response: Annotated[str | None, "최종 AI 응답"]

    # 지식 그래프 검색 필드
    mit_mention_needs_search: Annotated[bool, "KG 검색 필요 여부"]
    mit_mention_search_query: Annotated[str | None, "검색 쿼리 (추출된)"]
    mit_mention_search_results: Annotated[list[dict] | None, "KG 검색 결과"]
