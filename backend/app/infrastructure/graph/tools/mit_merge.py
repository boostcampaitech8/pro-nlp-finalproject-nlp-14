"""MIT Merge Tool - 결정사항 병합 처리

모든 참가자가 approved 상태인 결정사항을 latest로 승격하고,
동일 안건의 이전 latest를 outdated로 대체(SUPERSEDES)함.

Note: mit_merge는 참가자 전원 승인이 완료된 후 호출되어야 함.
      승인 확인은 호출 전에 외부에서 처리.
"""

import logging
from dataclasses import dataclass

from app.infrastructure.graph.deps import GraphDeps

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


@dataclass
class MergeResult:
    """Merge 결과"""

    success: bool
    decision_id: str
    new_status: str | None = None
    superseded_decisions: list[dict] | None = None
    error: str | None = None


async def execute_mit_merge(decision_id: str) -> MergeResult:
    """결정사항 병합 실행

    참가자 전원 승인이 완료된 결정사항에 대해:
    1. Decision (draft) -> Decision (latest)로 상태 변경
    2. 동일 안건의 이전 latest Decision -> outdated로 변경 (SUPERSEDES)

    Note: 이 함수는 참가자 전원 승인이 완료된 후 호출되어야 함.

    Args:
        decision_id: 병합할 결정사항 ID

    Returns:
        MergeResult: 병합 결과
    """
    logger.info(f"MIT Merge 시작: decision_id={decision_id}")

    repo = GraphDeps.get_graph_repo()

    # 1. 결정사항 조회
    decision = await repo.get_decision(decision_id)
    if not decision:
        logger.error(f"결정사항을 찾을 수 없음: {decision_id}")
        return MergeResult(
            success=False,
            decision_id=decision_id,
            error=f"Decision not found: {decision_id}",
        )

    # 2. draft 상태가 아니면 병합 불가
    if decision.get("status") != "draft":
        logger.warning(f"draft 상태가 아닌 결정사항: status={decision.get('status')}")
        return MergeResult(
            success=False,
            decision_id=decision_id,
            error=f"Decision is not in draft status: {decision.get('status')}",
        )

    # 3. draft -> latest 승격
    promoted = await repo.promote_decision_to_latest(decision_id)
    if not promoted:
        logger.error(f"결정사항 승격 실패: {decision_id}")
        return MergeResult(
            success=False,
            decision_id=decision_id,
            error="Failed to promote decision to latest",
        )

    logger.info(f"결정사항 승격 완료: {decision_id} -> latest")

    # 4. 동일 안건의 이전 latest -> outdated (SUPERSEDES)
    agenda_id = decision.get("agenda_id")
    superseded = []
    if agenda_id:
        superseded = await repo.supersede_previous_decisions(agenda_id, decision_id)
        if superseded:
            logger.info(
                f"이전 결정사항 대체: {[d['id'] for d in superseded]} -> outdated"
            )

    return MergeResult(
        success=True,
        decision_id=decision_id,
        new_status="latest",
        superseded_decisions=superseded,
    )


async def execute_mit_merge_batch(decision_ids: list[str]) -> list[MergeResult]:
    """여러 결정사항 일괄 병합

    Args:
        decision_ids: 병합할 결정사항 ID 목록

    Returns:
        병합 결과 목록
    """
    results = []
    for decision_id in decision_ids:
        result = await execute_mit_merge(decision_id)
        results.append(result)
    return results


async def auto_merge_meeting_decisions(meeting_id: str) -> list[MergeResult]:
    """회의의 모든 draft 결정사항 자동 병합

    회의 종료 시 모든 draft 결정사항을 일괄 병합.

    Args:
        meeting_id: 회의 ID

    Returns:
        병합 결과 목록
    """
    logger.info(f"회의 결정사항 자동 병합 시작: meeting_id={meeting_id}")

    repo = GraphDeps.get_graph_repo()

    # 회의의 draft 결정사항 조회
    draft_decisions = await repo.get_decisions_for_review(meeting_id)
    if not draft_decisions:
        logger.info("병합할 draft 결정사항 없음")
        return []

    logger.info(f"병합 대상 결정사항: {len(draft_decisions)}개")

    # 일괄 병합 실행
    decision_ids = [d["id"] for d in draft_decisions]
    results = await execute_mit_merge_batch(decision_ids)

    success_count = sum(1 for r in results if r.success)
    logger.info(f"병합 완료: {success_count}/{len(results)}개 성공")

    return results
