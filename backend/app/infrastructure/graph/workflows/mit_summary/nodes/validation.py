"""모순 감지 노드"""

import logging

from app.infrastructure.graph.schema.models import Contradiction, GTDecision, Utterance
from app.infrastructure.graph.workflows.mit_summary.state import MitSummaryState

logger = logging.getLogger(__name__)


async def detect_contradictions(state: MitSummaryState) -> MitSummaryState:
    """GT와 발화 비교하여 모순 감지

    Contract:
        reads: mit_summary_utterances_raw, mit_summary_gt_decisions
        writes: mit_summary_contradictions
        side-effects: LLM API 호출 (semantic matching)
        failures: CONTRADICTION_CHECK_FAILED -> errors 기록 (빈 결과 반환)

    구현 전략:
    1. GT Decision과 발화 텍스트를 semantic similarity로 비교
    2. 높은 유사도이지만 내용이 상반되는 경우 모순으로 감지
    3. LLM으로 모순 여부 및 심각도 판단
    4. Contradiction 리스트 생성
    """
    logger.info("모순 감지 시작")

    utterances = state.get("mit_summary_utterances_raw", [])
    gt_decisions = state.get("mit_summary_gt_decisions", [])

    if not utterances or not gt_decisions:
        logger.info("모순 감지할 데이터 없음 (utterances 또는 GT 비어있음)")
        return MitSummaryState(mit_summary_contradictions=[])

    try:
        # GT 연동 후 구현 예정
        contradictions: list[Contradiction] = []
        logger.info("모순 감지 완료: 0개 (GT 연동 대기 중)")
        return MitSummaryState(mit_summary_contradictions=contradictions)

    except Exception as e:
        logger.exception("모순 감지 실패")
        return MitSummaryState(
            mit_summary_contradictions=[],
            mit_summary_errors={
                "detect_contradictions": f"CONTRADICTION_CHECK_FAILED: {str(e)}"
            },
        )
