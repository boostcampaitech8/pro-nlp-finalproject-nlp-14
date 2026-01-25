"""mit_action State 정의

워크플로우 실행 중 공유되는 상태
"""

from typing import Annotated, TypedDict

from app.infrastructure.graph.schema.models import ActionItemData, ActionItemEvalResult


class MitActionState(TypedDict, total=False):
    """mit_action 서브그래프 State

    State 필드 prefix 규칙: 서브그래프 전용 필드는 mit_action_ prefix 사용
    """

    # 입력 필드
    mit_action_decision: Annotated[dict, "Decision 데이터 (확정된 결정사항)"]
    mit_action_meeting_id: Annotated[str, "회의 ID"]

    # 중간 상태 필드
    mit_action_raw_actions: Annotated[list[dict], "LLM이 추출한 raw Action Items"]
    mit_action_eval_result: Annotated[ActionItemEvalResult | None, "평가 결과"]
    mit_action_retry_reason: Annotated[str | None, "재시도 사유 (평가 실패 시)"]
    mit_action_retry_count: Annotated[int, "재시도 횟수"]

    # 출력 필드
    mit_action_actions: Annotated[list[ActionItemData], "저장된 Action Items"]
