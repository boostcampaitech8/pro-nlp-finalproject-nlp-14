"""Action Item 추출 노드"""

import logging

from app.infrastructure.graph.workflows.mit_action.state import (
    MitActionState,
)

logger = logging.getLogger(__name__)


async def extract_actions(state: MitActionState) -> MitActionState:
    """Decision에서 Action Item 추출

    Contract:
        reads: mit_action_decision, mit_action_retry_reason
        writes: mit_action_raw_actions
        side-effects: LLM API 호출
        failures: EXTRACTION_FAILED -> errors 기록
    """
    logger.info("Action Item 추출 시작")

    decision = state.get("mit_action_decision", {})
    retry_reason = state.get("mit_action_retry_reason")

    if retry_reason:
        logger.info(f"재시도 사유: {retry_reason}")

    # TODO: LLM을 사용하여 Decision에서 Action Item 추출
    # 1. Decision 내용 파싱
    # 2. Action Item 추출 프롬프트 구성
    # 3. LLM 호출
    # 4. 결과 파싱

    raw_actions: list[dict] = []  # TODO: 실제 추출 로직 구현

    logger.info(f"Action Item 추출 완료: {len(raw_actions)}개")

    return MitActionState(mit_action_raw_actions=raw_actions)
