"""Action Item 평가 노드"""

import logging

from app.infrastructure.graph.schema.models import ActionItemEvalResult
from app.infrastructure.graph.workflows.mit_action.state import (
    MitActionState,
)

logger = logging.getLogger(__name__)


async def evaluate_actions(state: MitActionState) -> MitActionState:
    """추출된 Action Item 품질 평가

    Contract:
        reads: mit_action_raw_actions
        writes: mit_action_eval_result
        side-effects: LLM API 호출
        failures: EVALUATION_FAILED -> errors 기록
    """
    logger.info("Action Item 평가 시작")

    raw_actions = state.get("mit_action_raw_actions", [])

    # TODO: LLM을 사용하여 추출 품질 평가
    # 1. 각 Action Item의 명확성 평가
    # 2. 담당자 지정 적절성 평가
    # 3. 기한 추출 정확성 평가
    # 4. 전체 점수 산출

    eval_result = ActionItemEvalResult(
        passed=True,  # TODO: 실제 평가 로직 구현
        reason="평가 로직 미구현 (스켈레톤)",
        score=0.0,
    )

    logger.info(f"Action Item 평가 완료: passed={eval_result.passed}")

    return MitActionState(mit_action_eval_result=eval_result)
