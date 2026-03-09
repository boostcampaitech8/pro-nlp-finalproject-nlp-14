"""KG 저장 노드

Meeting-Agenda-Decision을 Neo4j에 원홉으로 저장
"""

import logging

from app.core.neo4j import get_neo4j_driver
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState
from app.repositories.kg.repository import KGRepository

logger = logging.getLogger(__name__)


async def save_to_kg(state: GeneratePrState) -> GeneratePrState:
    """Meeting-Agenda-Decision을 Neo4j에 원홉으로 저장

    Contract:
        reads: generate_pr_meeting_id, generate_pr_agendas, generate_pr_summary
        writes: generate_pr_agenda_ids, generate_pr_decision_ids
        side-effects: Neo4j 쓰기 (1회 Cypher)

    Note: Minutes = Meeting + Agenda + Decision의 Projection (별도 노드 없음)
    """
    meeting_id = state.get("generate_pr_meeting_id")
    agendas = state.get("generate_pr_agendas", [])
    summary = state.get("generate_pr_summary", "")

    if not meeting_id:
        logger.error("meeting_id가 없습니다")
        return GeneratePrState(
            generate_pr_agenda_ids=[],
            generate_pr_decision_ids=[],
        )

    if not agendas:
        logger.warning("추출된 agendas가 없습니다")
        return GeneratePrState(
            generate_pr_agenda_ids=[],
            generate_pr_decision_ids=[],
        )

    logger.info(f"KG 저장 시작: meeting={meeting_id}, agendas={len(agendas)}")

    try:
        driver = get_neo4j_driver()
        kg_repo = KGRepository(driver)

        # create_minutes로 Meeting-Agenda-Decision 원홉 생성
        minutes = await kg_repo.create_minutes(
            meeting_id=meeting_id,
            summary=summary,
            agendas=agendas,
        )

        # Minutes에서 agenda_ids, decision_ids 추출
        agenda_ids = []
        decision_ids = []

        # get_minutes가 반환하는 KGMinutes에서 decision IDs 추출
        for decision in minutes.decisions:
            decision_ids.append(decision.id)

        # agenda_ids는 현재 KGMinutes에 없으므로 decisions에서 유추하거나 별도 조회
        # 현재 구조상 agenda_ids는 create_minutes 내부에서만 사용되고 반환하지 않음
        # 일단 decision_ids만 반환

        logger.info(
            f"KG 저장 완료: meeting={meeting_id}, "
            f"decisions={len(decision_ids)}"
        )

        return GeneratePrState(
            generate_pr_agenda_ids=agenda_ids,
            generate_pr_decision_ids=decision_ids,
        )

    except Exception as e:
        logger.error(f"KG 저장 실패: {e}")
        return GeneratePrState(
            generate_pr_agenda_ids=[],
            generate_pr_decision_ids=[],
        )
