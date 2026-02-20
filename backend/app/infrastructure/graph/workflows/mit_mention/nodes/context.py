"""컨텍스트 수집 노드"""

import logging

from app.core.neo4j import get_neo4j_driver
from app.repositories.kg.repository import KGRepository
from app.infrastructure.graph.workflows.mit_mention.state import (
    MitMentionState,
)

logger = logging.getLogger(__name__)


async def gather_context(state: MitMentionState) -> dict:
    """Decision 컨텍스트 수집

    Contract:
        reads: mit_mention_decision_content, mit_mention_decision_context, 
               mit_mention_thread_history, mit_mention_meeting_id, mit_mention_search_results
        writes: mit_mention_gathered_context
        side-effects: Neo4j 쿼리 (Meeting 컨텍스트 조회)
        failures: None (always succeeds with available data)
    """
    decision_content = state.get("mit_mention_decision_content", "")
    decision_context = state.get("mit_mention_decision_context") or ""
    thread_history = state.get("mit_mention_thread_history") or []
    search_results = state.get("mit_mention_search_results")  # 검색 결과 추가

    # Meeting 컨텍스트 추가
    meeting_id = state.get("mit_mention_meeting_id")
    meeting_context = None
    if meeting_id:
        try:
            driver = get_neo4j_driver()
            kg_repo = KGRepository(driver)
            meeting_context = await kg_repo.get_meeting_context(meeting_id)
            logger.info(f"[gather_context] Meeting context fetched: {meeting_id}")
        except Exception as e:
            logger.warning(f"[gather_context] Failed to fetch meeting context: {e}")
            meeting_context = None

    gathered = {
        "decision_summary": decision_content[:800],  # 요약 (500→800자로 확대)
        "decision_context": decision_context[:500] if decision_context else None,  # 300→500자로 확대
        "conversation_history": [
            {"role": h.get("role", "user"), "content": h.get("content", "")}
            for h in thread_history[-10:]  # 최근 5개→10개로 확대
        ],
        "meeting_context": meeting_context,
        "search_results": search_results,  # 검색 결과 포함
    }

    logger.info(
        f"[gather_context] Context gathered: {len(gathered['conversation_history'])} history items, "
        f"meeting_context={'present' if meeting_context else 'absent'}, "
        f"search_results={'present' if search_results else 'absent'}"
    )

    return {"mit_mention_gathered_context": gathered}
