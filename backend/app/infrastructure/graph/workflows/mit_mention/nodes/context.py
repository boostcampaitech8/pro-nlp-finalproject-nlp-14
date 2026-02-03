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
        reads: mit_mention_decision_content, mit_mention_decision_context, mit_mention_thread_history, mit_mention_meeting_id
        writes: mit_mention_gathered_context
        side-effects: Neo4j 쿼리 (Meeting 컨텍스트 조회)
        failures: None (always succeeds with available data)
    """
    decision_content = state.get("mit_mention_decision_content", "")
    decision_context = state.get("mit_mention_decision_context") or ""
    thread_history = state.get("mit_mention_thread_history") or []

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
        "decision_summary": decision_content[:500],  # 요약
        "decision_context": decision_context[:300] if decision_context else None,
        "conversation_history": [
            {"role": h.get("role", "user"), "content": h.get("content", "")}
            for h in thread_history[-5:]  # 최근 5개만
        ],
        "meeting_context": meeting_context,
    }

    logger.info(f"[gather_context] Context gathered: {len(gathered['conversation_history'])} history items, meeting_context={'present' if meeting_context else 'absent'}")

    return {"mit_mention_gathered_context": gathered}
