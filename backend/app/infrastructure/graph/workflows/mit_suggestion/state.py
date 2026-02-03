"""mit_suggestion State 정의

Suggestion을 반영하여 새로운 Decision 내용을 생성하는 워크플로우 상태
"""

from typing import Annotated, TypedDict


class MitSuggestionState(TypedDict, total=False):
    """mit_suggestion 워크플로우 State

    목적: Suggestion을 반영하여 새로운 Decision 내용 생성

    State 필드 prefix 규칙: 워크플로우 전용 필드는 mit_suggestion_ prefix 사용
    """

    # 입력 필드
    mit_suggestion_id: Annotated[str, "Suggestion ID"]
    mit_suggestion_content: Annotated[str, "Suggestion 내용 (사용자 제안)"]
    mit_suggestion_decision_id: Annotated[str, "원본 Decision ID"]
    mit_suggestion_decision_content: Annotated[str, "원본 Decision 내용"]
    mit_suggestion_decision_context: Annotated[str | None, "원본 Decision 맥락 (회의 컨텍스트)"]
    mit_suggestion_agenda_topic: Annotated[str | None, "Agenda 주제"]
    mit_suggestion_meeting_id: Annotated[str | None, "Meeting ID"]

    # 컨텍스트 수집 결과 (context_gatherer 출력)
    mit_suggestion_gathered_context: Annotated[dict | None, "수집된 컨텍스트"]

    # 출력 필드 (새 Decision 생성용)
    mit_suggestion_new_decision_content: Annotated[str | None, "AI가 생성한 새 Decision 내용"]
    mit_suggestion_supersedes_reason: Annotated[str | None, "대체 사유 (SUPERSEDES 관계에 저장)"]
    mit_suggestion_confidence: Annotated[str | None, "AI 신뢰도 (low/medium/high)"]
