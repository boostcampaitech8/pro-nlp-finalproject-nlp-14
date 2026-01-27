"""Action Item 저장 노드"""

import logging

from app.infrastructure.graph.schema.models import ActionItemData
from app.infrastructure.graph.workflows.mit_action.state import (
    MitActionState,
)

logger = logging.getLogger(__name__)


async def save_actions(state: MitActionState) -> MitActionState:
    """Action Item을 GraphDB에 저장

    Contract:
        reads: mit_action_raw_actions, mit_action_meeting_id, mit_action_decision
        writes: mit_action_actions
        side-effects: GraphDB 쓰기
        failures: SAVE_FAILED -> errors 기록

    NOTE: GraphDB 스키마 확정 후 구현. 현재는 스켈레톤만.
    """
    logger.info("Action Item 저장 시작")

    raw_actions = state.get("mit_action_raw_actions", [])
    meeting_id = state.get("mit_action_meeting_id")
    decision = state.get("mit_action_decision", {})

    # TODO: GraphDB에 Action Item 저장
    # 1. raw_actions를 ActionItemData로 변환
    # 2. GraphDB 연결
    # 3. 저장 실행
    # 4. 저장된 Action Item 목록 반환

    actions: list[ActionItemData] = []
    for raw in raw_actions:
        action = ActionItemData(
            content=raw.get("content", ""),
            assignee_id=raw.get("assignee_id"),
            assignee_name=raw.get("assignee_name"),
            deadline=raw.get("deadline"),
            confidence=raw.get("confidence", 0.0),
        )
        actions.append(action)

    logger.info(f"Action Item 저장 완료: {len(actions)}개 (스켈레톤)")

    return MitActionState(mit_action_actions=actions)
