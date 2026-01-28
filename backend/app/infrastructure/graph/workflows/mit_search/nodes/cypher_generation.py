"""FULLTEXT 검색을 위한 Cypher 쿼리 생성 노드."""

import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.graph.integration.llm import get_cypher_generator_llm

from ..state import MitSearchState

logger = logging.getLogger(__name__)


async def cypher_generator_async(state: MitSearchState) -> dict:
    """LLM으로 Neo4j FULLTEXT 검색용 Cypher 쿼리 생성.

    Contract:
        reads: mit_search_query, mit_search_filters, user_id
        writes: mit_search_cypher (실행 가능한 Cypher 쿼리 문자열)
        side-effects: LLM API 호출
        failures: LLM 오류/빈 응답 → 빈 쿼리 반환
    """
    logger.info("Starting Cypher generation")

    try:
        query = state.get("mit_search_query", "")
        filters = state.get("mit_search_filters", {})
        user_id = state.get("user_id", "")

        # 쿼리가 비어있으면 에러
        if not query:
            logger.warning("Empty query, cannot generate Cypher")
            return {"mit_search_cypher": ""}

        # Cypher 쿼리 생성 (LLM 기반)
        cypher = await _build_cypher_with_llm(query, filters, user_id)

        logger.info(f"Generated Cypher query ({len(cypher)} chars)")
        logger.debug(f"Cypher:\n{cypher}")

        return {"mit_search_cypher": cypher}

    except Exception as e:
        logger.error(f"Cypher generation failed: {e}", exc_info=True)
        # 실패 시 빈 쿼리 반환 (파이프라인은 계속)
        return {"mit_search_cypher": ""}


async def _build_cypher_with_llm(query: str, filters: dict, user_id: str) -> str:
    """LLM으로 Cypher 쿼리를 생성하고 문자열만 반환."""
    llm = get_cypher_generator_llm()

    system_prompt = """당신은 Neo4j Cypher 쿼리 생성기입니다.
반드시 실행 가능한 Cypher 문자열만 출력하세요. 설명이나 코드블록은 금지입니다.

요구사항:
1) FULLTEXT 인덱스: decision_search
2) FULLTEXT 호출:
   CALL db.index.fulltext.queryNodes('decision_search', $query) YIELD node, score
3) 회의 연결:
   MATCH (m:Meeting)-[:HAS_DECISION]->(node)
4) 사용자 권한 필터(필수):
   (m)<-[:PARTICIPATED_IN]-(:User {user_id: $user_id})
5) date_range가 있으면 node.decided_at >= date($start_date) AND node.decided_at <= date($end_date)
6) RETURN 필드:
   node.decision_id AS id, node.title AS title, node.content AS content,
   node.decided_at AS decided_at, m.meeting_id AS meeting_id,
   m.title AS meeting_title, score
7) ORDER BY score DESC
8) LIMIT 20
"""

    user_message = (
        f"query: {query}\n"
        f"user_id: {user_id}\n"
        f"filters: {filters}"
    )

    response = await llm.ainvoke([
        SystemMessage(system_prompt),
        HumanMessage(user_message),
    ])

    return response.content.strip()


def cypher_generator(state: MitSearchState) -> dict:
    """동기 테스트용 래퍼."""
    return asyncio.run(cypher_generator_async(state))
