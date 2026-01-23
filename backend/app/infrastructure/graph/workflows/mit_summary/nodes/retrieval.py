"""데이터 조회 노드

Orchestration에서 이미 필터링된 messages가 전달되므로,
여기서는 messages를 발화 구조로 변환하고 GT만 조회합니다.
"""

import logging
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage

from app.infrastructure.graph.schema.models import Utterance
from app.infrastructure.graph.workflows.mit_summary.state import MitSummaryState

logger = logging.getLogger(__name__)


def extract_utterances_from_messages(state: MitSummaryState) -> MitSummaryState:
    """OrchestrationState의 messages에서 발화 추출

    Contract:
        reads: messages
        writes: mit_summary_utterances_raw, mit_summary_metadata
        side-effects: none
        failures: MESSAGES_EMPTY -> errors 기록

    설계 결정:
    - OrchestrationState의 messages에 이미 필터링된 발화가 들어옴
    - DB/Redis 조회 불필요 (Orchestration 단계에서 처리됨)
    - messages를 Utterance 구조로 변환만 수행
    """
    logger.info("messages에서 발화 추출 시작")

    messages = state.get("messages", [])

    if not messages:
        logger.warning("messages가 비어있음")
        return MitSummaryState(
            mit_summary_utterances_raw=[],
            mit_summary_metadata={"source": "messages", "utterance_count": 0},
            mit_summary_errors={"extract_utterances": "MESSAGES_EMPTY"},
        )

    try:
        utterances: list[Utterance] = []

        for msg in messages:
            if isinstance(msg, (HumanMessage, AIMessage)):
                utterances.append(
                    Utterance(
                        speaker_id=getattr(msg, "name", "user"),
                        speaker_name=getattr(msg, "name", "User"),
                        text=msg.content,
                        start_time=0,
                        end_time=0,
                        timestamp=datetime.utcnow(),
                    )
                )

        logger.info(f"발화 추출 완료: {len(utterances)}개")

        metadata = {
            "source": "messages",
            "utterance_count": len(utterances),
            "message_count": len(messages),
            "extracted_at": datetime.utcnow().isoformat(),
        }

        return MitSummaryState(
            mit_summary_utterances_raw=utterances, mit_summary_metadata=metadata
        )

    except Exception as e:
        logger.exception("발화 추출 실패")
        return MitSummaryState(
            mit_summary_errors={"extract_utterances": f"EXTRACTION_FAILED: {str(e)}"}
        )


async def retrieve_gt_decisions(state: MitSummaryState) -> MitSummaryState:
    """GT에서 latest Decision 조회 (모순 감지용)

    Contract:
        reads: team_id, mit_summary_filter_params
        writes: mit_summary_gt_decisions
        side-effects: GT DB (Knowledge Graph) 조회
        failures: GT_QUERY_FAILED -> errors 기록

    구현 전략:
    1. team_id로 해당 팀의 GT 접근
    2. latest 상태인 Decision만 필터링
    3. filter_params에 토픽이 있으면 관련 Decision만 조회
    4. GTDecision 리스트로 변환
    """
    logger.info("GT Decision 조회 시작")

    team_id = state.get("team_id")
    filter_params = state.get("mit_summary_filter_params", {})

    try:
        # GT 연동은 Phase 2에서 구현 예정
        gt_decisions = []
        logger.info("GT Decision 조회 완료: 0개 (GT 연동 대기 중)")
        return MitSummaryState(mit_summary_gt_decisions=gt_decisions)

    except Exception as e:
        logger.exception("GT 조회 실패")
        return MitSummaryState(
            mit_summary_errors={"retrieve_gt_decisions": f"GT_QUERY_FAILED: {str(e)}"}
        )
