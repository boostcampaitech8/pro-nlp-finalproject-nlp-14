"""Action Item 저장 노드"""

import logging
from uuid import uuid4

from app.core.neo4j import get_neo4j_driver
from app.infrastructure.graph.schema.models import ActionItemData
from app.infrastructure.graph.workflows.mit_action.state import (
    MitActionState,
)
from app.repositories.kg.repository import KGRepository

logger = logging.getLogger(__name__)


async def save_actions(state: MitActionState) -> MitActionState:
    """Action Item을 GraphDB에 저장

    Contract:
        reads: mit_action_raw_actions, mit_action_meeting_id, mit_action_decision
        writes: mit_action_actions
        side-effects: GraphDB 쓰기
        failures: SAVE_FAILED -> errors 기록
    """
    logger.info("Action Item 저장 시작")

    raw_actions = state.get("mit_action_raw_actions", [])
    decision = state.get("mit_action_decision", {})
    decision_id = decision.get("id")

    if not decision_id:
        logger.warning("decision_id가 없습니다. 저장 스킵.")
        return MitActionState(mit_action_actions=[])

    if not raw_actions:
        logger.info("저장할 Action Item이 없습니다.")
        return MitActionState(mit_action_actions=[])

    try:
        driver = get_neo4j_driver()
        kg_repo = KGRepository(driver)

        # raw_actions -> Neo4j 저장용 데이터 (필드명 동일)
        items_to_create = []
        for raw in raw_actions:
            items_to_create.append({
                "id": f"action-{uuid4()}",
                "title": raw.get("title", ""),
                "description": raw.get("description"),
                "due_date": raw.get("due_date"),
                "assignee_id": raw.get("assignee_id"),
            })

        # 일괄 생성
        created_ids = await kg_repo.create_action_items_batch(
            decision_id=decision_id,
            action_items=items_to_create,
        )

        # ActionItemData로 변환하여 반환 (워크플로우 상태용)
        actions: list[ActionItemData] = []
        for raw in raw_actions:
            action = ActionItemData(
                title=raw.get("title", ""),
                description=raw.get("description"),
                due_date=raw.get("due_date"),
                assignee_id=raw.get("assignee_id"),
                assignee_name=raw.get("assignee_name"),
                confidence=raw.get("confidence", 0.0),
            )
            actions.append(action)

        logger.info(f"Action Item 저장 완료: {len(created_ids)}개")

        return MitActionState(mit_action_actions=actions)

    except Exception as e:
        logger.error(f"Action Item 저장 실패: {e}")
        # 에러 시에도 빈 리스트 반환 (워크플로우 계속 진행)
        return MitActionState(mit_action_actions=[])
