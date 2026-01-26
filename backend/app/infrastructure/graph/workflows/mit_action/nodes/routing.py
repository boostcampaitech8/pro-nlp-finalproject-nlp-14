"""평가 결과 라우팅 함수"""

import logging

from app.infrastructure.graph.config import MAX_RETRY
from app.infrastructure.graph.workflows.mit_action.state import (
    MitActionState,
)

logger = logging.getLogger(__name__)


def route_eval(state: MitActionState) -> str:
    """평가 결과에 따라 다음 노드 결정

    Contract:
        reads: mit_action_eval_result, mit_action_retry_count
        returns: 'extractor' (재시도) 또는 'saver' (저장 진행)

    NOTE: 라우팅 함수는 노드로 등록하지 않고 conditional_edge에 직접 연결
    """
    eval_result = state.get("mit_action_eval_result")
    retry_count = state.get("mit_action_retry_count", 0)

    if eval_result is None:
        logger.warning("eval_result가 없음, 저장 진행")
        return "saver"

    if eval_result.passed:
        logger.info("평가 통과, 저장 진행")
        return "saver"

    if retry_count >= MAX_RETRY:
        logger.warning(f"최대 재시도 횟수 초과 ({retry_count}), 저장 진행")
        return "saver"

    logger.info(f"평가 실패, 재시도 ({retry_count + 1}/{MAX_RETRY})")
    return "extractor"
