"""전략 기반 Cypher 쿼리 생성 노드."""

import asyncio
import json
import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from app.infrastructure.graph.integration.llm import get_generator_llm

from ..state import MitSearchState
from ..utils.search_strategy_router import SearchStrategyRouter
from ..nodes.tool_retrieval import _normalize_query, _generate_cypher_by_strategy

logger = logging.getLogger(__name__)


async def _generate_text_to_cypher(query: str, query_intent: dict, user_id: str) -> str:
    """LLM을 사용하여 자연어 쿼리를 Neo4j Cypher로 변환
    
    Args:
        query: 자연어 검색 쿼리
        query_intent: 쿼리 의도 분석 결과
        user_id: 사용자 ID
        
    Returns:
        생성된 Cypher 쿼리 또는 빈 문자열 (실패 시)
    """
    llm = get_generator_llm()
    
    schema_info = """
    Neo4j 스키마:
    노드 타입:
    - Meeting: {id, title, date, created_at}
    - Agenda: {id, title, created_at}
    - Decision: {id, content, status, created_at}
    - ActionItem: {id, title, status, due_date, created_at}
    - User: {id, name, email, role}
    - Team: {id, name, description}
    
    관계:
    - (Meeting)-[:CONTAINS]->(Agenda)
    - (Agenda)-[:HAS_DECISION]->(Decision)
    - (Agenda)-[:HAS_ACTION]->(ActionItem)
    - (User)-[:PARTICIPATED_IN]->(Meeting)
    - (User)-[:ASSIGNED_TO]->(ActionItem)
    - (User)-[:MEMBER_OF]->(Team)
    - (User)-[:ASSIGNED_TO]->(ActionItem)
    - (User)-[:PARTICIPATED_IN]->(Meeting)
    
    FULLTEXT 인덱스: decision_search (Decision 노드의 content 필드)
    """
    
    intent_type = query_intent.get("intent_type", "general_search")
    search_focus = query_intent.get("search_focus")
    primary_entity = query_intent.get("primary_entity")

    logger.info(
        "[Text-to-Cypher] 요청",
        extra={
            "query": query,
            "intent_type": intent_type,
            "search_focus": search_focus,
            "primary_entity": primary_entity,
        },
    )
    
    system_prompt = f"""당신은 Neo4j Cypher 쿼리 생성 전문가입니다.
자연어 질문을 Neo4j Cypher 쿼리로 변환하세요.

{schema_info}

규칙:

1. 오직 Cypher 쿼리만 반환 (설명 없음)
2. **중요**: 존재하지 않는 관계/속성 사용 금지 (예: MADE_DECISION, Agenda.order)

현재 쿼리 의도:
- Intent: {intent_type}
- Focus: {search_focus or "일반"}
- Entity: {primary_entity or "없음"}

예시1 - 사람 이름으로 결정사항 검색:
질문: "신수효 관련 결정사항"
Cypher:
MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)
WHERE u.name CONTAINS $query AND (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
RETURN d.id AS id, d.content AS content, d.status AS status,
       m.title AS meeting_title, m.id AS meeting_id, 1.0 AS score
ORDER BY d.created_at DESC LIMIT 20

예시2 - 키워드로 검색:
질문: "교육 프로그램 담당자는 누구?"
Cypher:
CALL db.index.fulltext.queryNodes('decision_search', $query) YIELD node, score
MATCH (a:Agenda)-[:HAS_DECISION]->(node)
MATCH (m:Meeting)-[:CONTAINS]->(a)
WHERE (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
OPTIONAL MATCH (ai:ActionItem)<-[:HAS_ACTION]-(a)
OPTIONAL MATCH (u:User)-[:ASSIGNED_TO]->(ai)
RETURN node.id AS id, node.content AS content, ai.title AS action_title, 
       coalesce(u.name, "미배정") AS assignee, score
ORDER BY score DESC LIMIT 20

예시3 - 팀원 검색:
질문: "신수효와 같은 팀원은?"
Cypher:
MATCH (u:User)-[:MEMBER_OF]->(team:Team)
WHERE u.name CONTAINS $query
MATCH (team)<-[:MEMBER_OF]-(member:User)
WHERE member <> u
RETURN member.id AS id, member.name AS title, member.name AS content, 
       team.name AS team_name, 1.0 AS score
ORDER BY member.name ASC LIMIT 20
"""
    
    user_message = f"질문: {query}\n\nCypher 쿼리를 생성하세요:"
    
    try:
        response = await llm.ainvoke([
            SystemMessage(system_prompt),
            HumanMessage(user_message)
        ])
        
        cypher = response.content.strip()
        
        # 코드 블록 제거
        if cypher.startswith("```"):
            cypher = re.sub(r"```(?:cypher|sql)?\n?", "", cypher)
            cypher = cypher.strip("`").strip()
        
        # 기본 검증: MATCH/CALL 포함 확인
        if not any(keyword in cypher.upper() for keyword in ["MATCH", "CALL"]):
            logger.warning(f"[Text-to-Cypher] 유효하지 않은 Cypher: {cypher[:100]}")
            return ""
        
        cypher = _sanitize_generated_cypher(cypher)
        logger.info(f"[Text-to-Cypher] 생성 성공: {len(cypher)} chars")
        logger.debug(f"[Text-to-Cypher] Cypher:\n{cypher}")
        return cypher
        
    except Exception as e:
        logger.error(f"[Text-to-Cypher] 생성 실패: {e}")
        return ""


async def cypher_generator_async(state: MitSearchState) -> Dict[str, Any]:
    """SearchStrategyRouter 기반 Cypher 쿼리 생성.

    Contract:
        reads: mit_search_query, mit_search_filters, mit_search_query_intent, user_id
        writes: mit_search_cypher, mit_search_strategy
        side-effects: None (순수 함수)
        failures: 전략 선택 실패 → 기본 fulltext Cypher 반환
    """
    print("[Cypher Generator] 진입")
    logger.info("[Cypher Generator] 시작")

    try:
        query = state.get("mit_search_query", "")
        filters = state.get("mit_search_filters", {})
        user_id = state.get("user_id", "")
        query_intent = state.get("mit_search_query_intent", {})

        print(f"[Cypher Generator] query={query}, intent={query_intent}")

        if not query:
            logger.warning("[Cypher Generator] 빈 쿼리")
            return {"mit_search_cypher": "", "mit_search_strategy": {}}

        # 정규화
        normalized_keywords = _normalize_query(query)
        logger.info(f"[Cypher Generator] 정규화: '{query}' → '{normalized_keywords}'")
        
        # 전략 결정
        entity_types = filters.get("entity_types", [])
        logger.info(f"[Cypher Generator] Intent: {query_intent.get('intent_type')}, Primary Entity: {query_intent.get('primary_entity')}")
        
        router = SearchStrategyRouter()
        strategy = router.determine_strategy(
            query_intent=query_intent,
            entity_types=entity_types,
            normalized_keywords=normalized_keywords,
            user_id=user_id
        )
        
        print(f"[Cypher Generator] 전략: {strategy['strategy']}")
        logger.info(
            f"[Cypher Generator] 전략 선택: {strategy['strategy']} (검색어: {strategy['search_term']})",
            extra={
                "strategy": strategy["strategy"],
                "search_term": strategy["search_term"],
            },
        )

        cypher = ""

        if strategy["strategy"] == "text_to_cypher":
            logger.info("[Cypher Generator] Text-to-Cypher 생성 시도")
            llm_cypher = await _generate_text_to_cypher(query, query_intent, user_id)

            if llm_cypher:
                cypher = llm_cypher
                strategy["reasoning"] = "LLM 생성 Cypher"
            else:
                logger.warning("[Cypher Generator] Text-to-Cypher 실패, fulltext 템플릿 fallback")
                cypher = _get_fulltext_template()
                strategy["reasoning"] = "LLM 실패 → fulltext fallback"
        else:
            # 템플릿 기반 전략
            cypher = _generate_cypher_by_strategy(
                strategy=strategy["strategy"],
                query_intent=query_intent,
                entity_types=entity_types,
                normalized_keywords=normalized_keywords,
                filters=filters,
                cypher_template=_get_fulltext_template(),
            )

        logger.info(f"Generated Cypher ({len(cypher)} chars)")
        logger.debug(f"Generated Cypher:\n{cypher}")
        
        # 생성된 Cypher를 콘솔에 출력
        print(f"\n[Cypher 생성됨]\n{cypher}\n")

        return {"mit_search_cypher": cypher, "mit_search_strategy": strategy}

    except Exception as e:
        logger.error(f"Cypher generation failed: {e}", exc_info=True)
        return {"mit_search_cypher": "", "mit_search_strategy": {}}


def _get_fulltext_template() -> str:
    """FULLTEXT 검색용 기본 템플릿"""
    return """CALL db.index.fulltext.queryNodes('decision_search', $query)
YIELD node, score
MATCH (a:Agenda)-[:HAS_DECISION]->(node)
MATCH (m:Meeting)-[:CONTAINS]->(a)
WHERE (m)<-[:PARTICIPATED_IN]-(:User {id: $user_id})
RETURN node.id AS id, node.content AS content, node.status AS status, node.created_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, score
ORDER BY score DESC, node.created_at DESC
LIMIT 20"""


def _sanitize_generated_cypher(cypher: str) -> str:
    """LLM 생성 Cypher의 흔한 오류를 보정합니다."""
    # 존재하지 않는 관계/속성 제거
    cypher = re.sub(r":MADE_DECISION\b", "", cypher)
    cypher = re.sub(r"\b(a\.|agenda\.)order\b", "a.title", cypher, flags=re.IGNORECASE)

    # OPTIONAL MATCH (u:User)-[]->(node) 제거
    cypher = re.sub(
        r"OPTIONAL MATCH\s*\(u:User\)\s*-\s*\[\s*\]\s*->\s*\(node\)\s*\n?",
        "",
        cypher,
        flags=re.IGNORECASE,
    )

    # maker/assignee 필드가 남아있으면 제거
    cypher = re.sub(
        r',\s*coalesce\(u\.name,\s*"[^"]*"\)\s+AS\s+\w+',
        "",
        cypher,
        flags=re.IGNORECASE,
    )

    upper = cypher.upper()
    if "ORDER BY" in upper:
        parts = re.split(r"ORDER BY", cypher, flags=re.IGNORECASE)
        pre_order = parts[0]
        post_order = "ORDER BY" + parts[1] if len(parts) > 1 else ""

        if re.search(r"ORDER BY\s+score\s+DESC,\s*created_at\s+DESC", post_order, re.IGNORECASE):
            if not re.search(r"\bcreated_at\b", pre_order):
                # created_at alias가 없으면 제거
                cypher = re.sub(
                    r"ORDER BY\s+score\s+DESC,\s*created_at\s+DESC",
                    "ORDER BY score DESC",
                    cypher,
                    flags=re.IGNORECASE,
                )

        if re.search(r"ORDER BY\s+created_at\s+DESC", post_order, re.IGNORECASE):
            if not re.search(r"\bcreated_at\b", pre_order):
                cypher = re.sub(
                    r"ORDER BY\s+created_at\s+DESC",
                    "",
                    cypher,
                    flags=re.IGNORECASE,
                )

    return cypher


def cypher_generator(state: MitSearchState) -> Dict[str, Any]:
    """동기 테스트용 래퍼."""
    return asyncio.run(cypher_generator_async(state))
