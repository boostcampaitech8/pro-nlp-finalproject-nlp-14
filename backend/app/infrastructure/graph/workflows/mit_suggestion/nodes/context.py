"""컨텍스트 수집 노드"""

import logging

from app.core.neo4j import get_neo4j_driver
from app.repositories.kg.repository import KGRepository
from app.infrastructure.graph.workflows.mit_suggestion.state import MitSuggestionState

logger = logging.getLogger(__name__)


async def gather_context(state: MitSuggestionState) -> dict:
    """Suggestion 처리를 위한 컨텍스트 수집

    Contract:
        reads: mit_suggestion_decision_id, mit_suggestion_meeting_id
        writes: mit_suggestion_gathered_context
        side-effects: Neo4j 읽기 쿼리
        failures: DB 오류 시 빈 컨텍스트 반환 (graceful degradation)

    수집 내용:
    1. meeting_context: 회의 제목, 날짜, agenda 주제들
    2. thread_history: 원본 Decision에 대한 Comment/Reply 이력 (논의 배경)
    3. sibling_decisions: 같은 Agenda의 다른 Decision들
    """
    decision_id = state.get("mit_suggestion_decision_id")
    meeting_id = state.get("mit_suggestion_meeting_id")
    decision_content = state.get("mit_suggestion_decision_content", "")

    gathered = {
        "decision_summary": decision_content[:500] if decision_content else "",
        "meeting_context": None,
        "thread_history": [],
        "sibling_decisions": [],
    }

    if not decision_id:
        logger.warning("[gather_context] No decision_id provided")
        return {"mit_suggestion_gathered_context": gathered}

    try:
        driver = get_neo4j_driver()
        kg_repo = KGRepository(driver)

        # 1. 회의 컨텍스트 조회
        if meeting_id:
            try:
                meeting_context = await kg_repo.get_meeting_context(meeting_id)
                if meeting_context:
                    gathered["meeting_context"] = meeting_context
                    logger.info(f"[gather_context] Meeting context gathered: {meeting_id}")
            except Exception as e:
                logger.warning(f"[gather_context] Failed to get meeting context: {e}")

        # 2. 원본 Decision에 대한 논의 이력 조회
        try:
            thread_history = await kg_repo.get_decision_thread_history(decision_id)
            if thread_history:
                # 최근 10개만, 각 코멘트는 200자로 제한
                gathered["thread_history"] = [
                    {
                        "role": h.get("role", "user"),
                        "content": h.get("content", "")[:200],
                        "author": h.get("author_name", "Unknown"),
                    }
                    for h in thread_history[-10:]
                ]
                logger.info(f"[gather_context] Thread history gathered: {len(gathered['thread_history'])} items")
        except Exception as e:
            logger.warning(f"[gather_context] Failed to get thread history: {e}")

        # 3. 같은 Agenda의 다른 Decision들 조회
        if meeting_id:
            try:
                minutes_view = await kg_repo.get_minutes_view(meeting_id)
                if minutes_view and minutes_view.get("agendas"):
                    # 현재 Decision이 속한 Agenda 찾기
                    current_agenda_topic = state.get("mit_suggestion_agenda_topic", "")
                    for agenda in minutes_view.get("agendas", []):
                        if agenda.get("topic") == current_agenda_topic:
                            # 같은 Agenda의 다른 Decision들 (현재 Decision 제외)
                            sibling_decisions = [
                                {
                                    "id": d.get("id"),
                                    "content": d.get("content", "")[:200],
                                    "status": d.get("status"),
                                }
                                for d in agenda.get("decisions", [])
                                if d.get("id") != decision_id
                            ][:5]  # 최대 5개
                            gathered["sibling_decisions"] = sibling_decisions
                            logger.info(f"[gather_context] Sibling decisions gathered: {len(sibling_decisions)} items")
                            break
            except Exception as e:
                logger.warning(f"[gather_context] Failed to get sibling decisions: {e}")

        logger.info(
            f"[gather_context] Context gathered: meeting={bool(gathered['meeting_context'])}, "
            f"threads={len(gathered['thread_history'])}, siblings={len(gathered['sibling_decisions'])}"
        )

    except Exception as e:
        logger.exception(f"[gather_context] Failed to gather context: {e}")

    return {"mit_suggestion_gathered_context": gathered}
