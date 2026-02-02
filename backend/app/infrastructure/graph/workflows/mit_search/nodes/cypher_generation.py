"""전략 기반 Cypher 쿼리 생성 노드 (CoT 및 Template Fallback 포함)."""

import asyncio
import json
import logging
import re
import textwrap
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.graph.integration.llm import get_cypher_generator_llm
from ..nodes.tool_retrieval import generate_cypher_by_strategy, normalize_query
from ..state import MitSearchState
from ..utils.search_strategy_router import SearchStrategyRouter
from ..utils.template_cypher import generate_template_cypher

logger = logging.getLogger(__name__)

# Cypher 생성 캐시 (최대 50개, FIFO)
_cypher_cache: Dict[str, str] = {}

FOCUS_RULES = {
    "Meeting": {
        "required": ["MEETING"],
        "forbidden": ["HAS_DECISION", "DECISION"],
        "fallback_reason": "meeting fallback",
    },
    "Decision": {
        "required": ["HAS_DECISION", "DECISION"],
        "forbidden": [],
        "fallback_reason": "fulltext fallback",
    },
    "User": {
        "required": ["MEMBER_OF", "USER"],
        "forbidden": [],
        "fallback_reason": "user fallback",
    },
}


async def _generate_text_to_cypher_raw(
    query: str,
    query_intent: dict,
    user_id: str,
    feedback: str | None = None,
) -> str:
    """LLM을 사용하여 자연어 쿼리를 Neo4j Cypher로 변환 (CoT 적용).

    Args:
        query: 자연어 검색 쿼리
        query_intent: 쿼리 의도 분석 결과
        user_id: 사용자 ID
        feedback: 이전 실패에 대한 피드백 (재시도 시 사용)

    Returns:
        생성된 Cypher 쿼리 문자열 (실패 시 빈 문자열)
    """
    llm = get_cypher_generator_llm()

    # 1. 스키마 정의
    schema_info = textwrap.dedent(
        """
        [Graph Schema]
        Nodes:
        - Team: {id, name, description}
        - User: {id, name, email}
        - Meeting: {id, title, status("scheduled", "ongoing", "completed", "in_review", "confirmed", "cancelled"),
                   description, summary, team_id, scheduled_at(datetime), started_at(datetime),
                   ended_at(datetime), created_at(datetime)}
        - Agenda: {id, topic, description, team_id, created_at(datetime)}
        - Decision: {id, content, status("draft", "latest", "outdated", "superseded", "rejected"),
                    context, meeting_id, team_id, created_at(datetime), updated_at(datetime)}
        - ActionItem: {id, content, status("pending", "in_progress", "completed", "cancelled"),
                      due_date(datetime), meeting_id, team_id, created_at(datetime)}
        - Suggestion: {id, content, status("pending", "accepted", "rejected"), author_id,
                      decision_id, created_decision_id, meeting_id, team_id, created_at(datetime)}
        - Comment: {id, content, author_id, decision_id, parent_id, team_id, created_at(datetime)}

        Relationships (Directional):
        - (:User)-[:MEMBER_OF {role}]->(:Team)
        - (:Team)-[:HOSTS]->(:Meeting)
        - (:User)-[:PARTICIPATED_IN {role}]->(:Meeting)
        - (:Meeting)-[:CONTAINS {order}]->(:Agenda)
        - (:Meeting)-[:DECIDED_IN]->(:Decision)
        - (:Agenda)-[:HAS_DECISION]->(:Decision)
        - (:User)-[:APPROVES]->(:Decision)
        - (:User)-[:REJECTS]->(:Decision)
        - (:Decision)-[:SUPERSEDES]->(:Decision)
        - (:Decision)-[:OUTDATES]->(:Decision)
        - (:Decision)-[:TRIGGERS]->(:ActionItem)
        - (:User)-[:ASSIGNED_TO]->(:ActionItem)
        - (:Team)-[:ASSIGNED_TO]->(:ActionItem)
        - (:User)-[:SUGGESTS]->(:Suggestion)
        - (:Suggestion)-[:CREATES]->(:Decision)
        - (:Suggestion)-[:ON]->(:Decision)
        - (:User)-[:COMMENTS]->(:Comment)
        - (:Comment)-[:ON]->(:Decision)
        - (:Comment)-[:REPLY_TO]->(:Comment)

        Indexes:
        - CALL db.index.fulltext.queryNodes('decision_search', 'keyword')
        - CALL db.index.fulltext.queryNodes('meeting_search', 'keyword')
        - CALL db.index.fulltext.queryNodes('comment_search', 'keyword')
        """
    ).strip()

    # 2. 시스템 프롬프트: Few-Shot 예시 추가 (가장 중요)
    system_prompt = textwrap.dedent(
        f"""
        Role: Neo4j Cypher Expert & Graph Navigator.

        Task:
        Convert the user's Natural Language Query into a precise Neo4j Cypher query based on the Schema.

        {schema_info}

                [Execution Principles]
                    1. **Security & Safety**:
                            - Only READ operations allowed.
                            - Do NOT use CREATE/DELETE/SET/MERGE/LOAD CSV/CALL except fulltext index call.
                            - Prefer scoping to the current user when possible.

                    2. **Intent Alignment (CRITICAL)**:
                            - Use the provided intent fields to choose the target node and filters.
                            - If intent specifies a person/team and a topic, filter BOTH.
                                `WHERE u.name CONTAINS $entity_name AND m.title CONTAINS $search_term`
                            - If a non-entity keyword exists, 반드시 CONTAINS 필터를 추가.
                            - Use EXACT literals; DO NOT TRANSLATE.

                    3. **Traversal**:
                            - Use the schema paths only (User → Meeting → Agenda → Decision, etc.).
                            - Team/Composite intent must follow Member/Assigned relationships.

                    4. **Formatting (CRITICAL - String Operations)**:
                            - Must return: id, title/content, created_at, score, graph_context.
                            - `graph_context` must be a human-readable string built with `+` operator.
                            - **NEVER use CONCAT() function - Neo4j does NOT support it!**
                            - **ONLY use + operator for string concatenation**
                            - Example: `u.name + '님이 참여한 회의: ' + m.title AS graph_context`
                            - Alias MUST be `AS graph_context`.
                            - ALWAYS end with `LIMIT 20`.
                            - No UNION/UNION ALL. Single query only.

        [Few-Shot Examples]
        Q: "민수랑 했던 예산 회의 찾아줘"
        ```thought
        1. Intent: Find meetings with '민수' containing keyword '예산'.
        2. Strategy: User -> Participated -> Meeting
        3. Entities: Name='민수'
        4. Keywords: Topic='예산' (Add to WHERE!)
        5. Composite Filter: User name AND Meeting title (both required)
        ```
        ```cypher
        MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)
        WHERE u.name CONTAINS '민수'
          AND m.title CONTAINS '예산'
        RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
               u.name + '님과 함께한 예산(Budget) 회의: ' + m.title AS graph_context
        ORDER BY m.created_at DESC
        LIMIT 20
        ```

        Q: "조우진이랑 UX 관련한 회의 찾아줘"
        ```thought
        1. Intent: Find meetings with '조우진' containing keyword 'UX'.
        2. Strategy: User -> Participated -> Meeting
        3. Entities: Name='조우진'
        4. Keywords: Topic='UX'
        5. Composite Filter: User name AND Meeting title (both required)
        ```
        ```cypher
        MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)
        WHERE u.name CONTAINS '조우진'
          AND m.title CONTAINS 'UX'
        RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
               u.name + '님이 참여한 UX 관련 회의: ' + m.title AS graph_context
        ORDER BY m.created_at DESC
        LIMIT 20
        ```

        Q: "회고가 포함된 미팅"
        ```thought
        1. Intent: Find meetings with keyword '회고'.
        2. Strategy: Direct Meeting search
        3. Entities: None
        4. Keywords: Topic='회고'
        ```
        ```cypher
        MATCH (m:Meeting)
        WHERE m.title CONTAINS '회고'
        RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
               '회고 관련 회의: ' + m.title AS graph_context
        ORDER BY m.created_at DESC
        LIMIT 20
        ```

        [Output Format]
        Follow the Thought process above.
        Format:
        ```thought
        1. Intent Analysis: ...
        2. Path Strategy: ...
        3. Entities: ...
        4. Keywords: ...
        5. Constraints: ...
        ```
        ```cypher
        ...
        ```
        """
    ).strip()

    # 의도 정보 주입
    keywords = query_intent.get('keywords', None)
    user_context = textwrap.dedent(
        f"""
        [Context]
        - UserID: {user_id}
        - Query: "{query}"
        - Analyzed Intent: {query_intent.get('intent_type', 'Unknown')}
        - Focus Entity: {query_intent.get('primary_entity', 'None')}
        - Target Node: {query_intent.get('search_focus', 'Any')}
        - Additional Keywords: {keywords if keywords else 'None'}
        - Date Range: {query_intent.get('date_range', None)}
        - Entity Types: {query_intent.get('entity_types', None)}

        [IMPORTANT]
        - If Focus Entity exists AND Additional Keywords exist: Use BOTH in WHERE clause
        - Example: WHERE u.name CONTAINS 'Entity' AND m.title CONTAINS 'Keyword'
        """
    ).strip()

    if feedback:
        user_context += (
            f"\n\n[Previous Error Feedback]\n{feedback}\nPlease fix the error and regenerate."
        )

    full_prompt = [
        SystemMessage(system_prompt),
        HumanMessage(user_context),
    ]

    try:
        response_content = ""
        print(f"\n[Text-to-Cypher] LLM 호출 시작 (Feedback: {bool(feedback)})...")
        # 스트리밍으로 응답 받기
        async for chunk in llm.astream(full_prompt):
            if hasattr(chunk, "content"):
                print(chunk.content, end="", flush=True)  # 디버깅용 실시간 출력
                response_content += chunk.content

        print("\n" + "=" * 50)

        # 3. 파싱 로직: Thought 블록과 Cypher 블록 분리
        cypher = ""

        # ```cypher ... ``` 블록 추출 우선 시도
        cypher_match = re.search(
            r"```cypher\s*(.*?)\s*```", response_content, re.DOTALL | re.IGNORECASE
        )
        if cypher_match:
            cypher = cypher_match.group(1).strip()
        else:
            # 포맷을 안 지켰을 경우, 기본적인 코드 블록 추출 시도
            code_block_match = re.search(
                r"```\s*(.*?)\s*```", response_content, re.DOTALL
            )
            if code_block_match:
                content = code_block_match.group(1).strip()
                # thought 블록이 아님을 확인
                if not content.lower().startswith("thought") and (
                    "MATCH" in content.upper() or "CALL" in content.upper()
                ):
                    cypher = content
            else:
                # 최후의 수단: MATCH나 CALL로 시작하는 부분부터 끝까지 추출
                match_start = re.search(
                    r"(MATCH|CALL)\s", response_content, re.IGNORECASE
                )
                if match_start:
                    cypher = response_content[match_start.start() :].strip()

        # 정제 및 검증
        cypher = _sanitize_generated_cypher(cypher)

        # 유효성 검사
        if not cypher or not any(
            k in cypher.upper() for k in ["MATCH", "CALL", "RETURN"]
        ):
            logger.warning("[Text-to-Cypher] 유효한 Cypher 추출 실패")
            return ""

        logger.info(f"[Text-to-Cypher] 생성 완료: {len(cypher)} chars")
        return cypher

    except Exception as e:
        logger.error(f"[Text-to-Cypher] 생성 중 에러: {e}")
        return ""


async def _generate_text_to_cypher(
    query: str, query_intent: dict, user_id: str
) -> str:
    """LLM Cypher 생성 + 품질/안전성 피드백 기반 재시도 (캐싱 포함)."""
    # 캐시 키 생성
    cache_key = f"{query}|{query_intent.get('intent_type')}|{query_intent.get('search_focus')}"

    # 캐시 확인
    if cache_key in _cypher_cache:
        logger.info(f"[Text-to-Cypher] 캐시 히트: {query}")
        return _cypher_cache[cache_key]

    subqueries = await _extract_subqueries(query)
    logger.info(
        "[Text-to-Cypher] 서브쿼리 분해 완료",
        extra={"count": len(subqueries), "subqueries": subqueries},
    )

    for subquery in subqueries:
        cypher = await _attempt_cypher_with_feedback(subquery, query_intent, user_id)
        if cypher:
            # 캐시에 저장 (최대 50개, FIFO)
            if len(_cypher_cache) >= 50:
                _cypher_cache.pop(next(iter(_cypher_cache)))
            _cypher_cache[cache_key] = cypher
            return cypher

    return ""


async def cypher_generator_async(state: MitSearchState) -> Dict[str, Any]:
    """SearchStrategyRouter 기반 Cypher 쿼리 생성 (Template Fallback 포함).

    Contract:
        reads: mit_search_query, mit_search_query_intent, user_id
        writes: mit_search_cypher, mit_search_strategy
    """
    start_time = time.time()
    print("[Cypher Generator] 진입")
    logger.info("[Cypher Generator] 시작")

    try:
        query = state.get("mit_search_query", "")
        user_id = state.get("user_id", "")
        query_intent = state.get("mit_search_query_intent", {})

        filters = {
            "date_range": query_intent.get("date_range"),
            "entity_types": query_intent.get("entity_types"),
        }

        print(f"[Cypher Generator] query={query}, intent={query_intent}")

        if not query:
            logger.warning("[Cypher Generator] 빈 쿼리")
            return {"mit_search_cypher": "", "mit_search_strategy": {}}

        # 정규화
        normalized_keywords = normalize_query(query)
        logger.info(f"[Cypher Generator] 정규화: '{query}' → '{normalized_keywords}'")

        # 전략 결정
        entity_types = filters.get("entity_types", [])
        router = SearchStrategyRouter()
        strategy = router.determine_strategy(
            query_intent=query_intent,
            entity_types=entity_types,
            normalized_keywords=normalized_keywords,
            user_id=user_id,
        )

        logger.info(
            f"[Cypher Generator] 전략 선택: {strategy['strategy']} (Fallback: {strategy.get('use_fallback', False)})"
        )

        cypher = ""

        # Case 1: Template 우선 전략
        if strategy["strategy"] == "template_based":
            logger.info("[Cypher Generator] Template 우선 시도")
            template_cypher = generate_template_cypher(
                intent_type=query_intent.get("intent_type"),
                search_focus=query_intent.get("search_focus"),
                primary_entity=query_intent.get("primary_entity"),
                keywords=query_intent.get("keywords"),
                user_id=user_id,
                date_filter=filters.get("date_range"),
            )

            if template_cypher:
                cypher = template_cypher
                strategy["reasoning"] = "Template (pattern matched)"
                logger.info("[Cypher Generator] ✓ Template 성공")
            else:
                logger.info("[Cypher Generator] Template 없음 → LLM Fallback")
                llm_cypher = await _generate_text_to_cypher(query, query_intent, user_id)
                if llm_cypher:
                    cypher = llm_cypher
                    strategy["reasoning"] = "Template 없음 → LLM Fallback"
                    logger.info("[Cypher Generator] ✓ LLM Fallback 성공")

        # Case 2: LLM 우선 전략
        elif strategy["strategy"] == "text_to_cypher":
            logger.info("[Cypher Generator] LLM 우선 시도")
            llm_cypher = await _generate_text_to_cypher(query, query_intent, user_id)

            if llm_cypher:
                cypher = llm_cypher
                strategy["reasoning"] = "LLM (text-to-cypher)"
                logger.info("[Cypher Generator] ✓ LLM 성공")

            # LLM 실패 시 Fallback
            elif strategy.get("use_fallback", False):
                logger.warning("[Cypher Generator] LLM 실패 → Template Fallback 시도")
                template_cypher = generate_template_cypher(
                    intent_type=query_intent.get("intent_type"),
                    search_focus=query_intent.get("search_focus"),
                    primary_entity=query_intent.get("primary_entity"),
                    keywords=query_intent.get("keywords"),
                    user_id=user_id,
                    date_filter=filters.get("date_range"),
                )

                if template_cypher:
                    cypher = template_cypher
                    strategy["reasoning"] = "LLM 실패 → Template Fallback"
                    strategy["strategy"] = "template_based"
                    logger.info("[Cypher Generator] ✓ Template Fallback 성공")
                else:
                    logger.warning("[Cypher Generator] Template도 없음 → fulltext fallback")
                    cypher, strategy = _apply_focus_fallback(
                        cypher, strategy, query_intent
                    )
            else:
                logger.warning(
                    "[Cypher Generator] LLM 실패 (Fallback 비활성화) → fulltext fallback"
                )
                cypher, strategy = _apply_focus_fallback(cypher, strategy, query_intent)

        else:
            # 기타 전략
            cypher = generate_cypher_by_strategy(
                strategy=strategy["strategy"],
                query_intent=query_intent,
                entity_types=entity_types,
                normalized_keywords=normalized_keywords,
                filters=filters,
                cypher_template=_get_fulltext_template(),
            )

        # 품질 검증 및 최종 출력
        quality_issues = _collect_cypher_issues(cypher, query_intent)
        if quality_issues:
            logger.warning(
                "[Cypher Generator] 품질/의도 검증 실패", extra={"issues": quality_issues}
            )
            # 심각한 이슈(보안 등)가 있으면 Fallback
            if "missing_user_scope" in quality_issues or "unsafe_cypher" in quality_issues:
                cypher, strategy = _apply_focus_fallback(cypher, strategy, query_intent)

        print(f"\n{'='*80}")
        print(f"[최종 실행 Cypher] (전략: {strategy['strategy']})")
        print(f"{'='*80}")
        print(cypher)
        print(f"{'='*80}\n")
        logger.info(f"[Cypher Generator] 완료 (소요시간: {time.time() - start_time:.2f}s)")

        return {"mit_search_cypher": cypher, "mit_search_strategy": strategy}

    except Exception as e:
        logger.error(f"Cypher generation failed: {e}", exc_info=True)
        return {"mit_search_cypher": "", "mit_search_strategy": {}}


# -------------------------------------------------------------------------
# Helper Functions & Templates
# -------------------------------------------------------------------------


def _get_fulltext_template() -> str:
    """FULLTEXT 검색용 기본 템플릿 (키워드 검색)"""
    return """CALL db.index.fulltext.queryNodes('decision_search', $query)
YIELD node, score
MATCH (a:Agenda)-[:HAS_DECISION]->(node)
MATCH (m:Meeting)-[:CONTAINS]->(a)
RETURN node.id AS id, node.content AS content, node.status AS status, node.created_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, score,
       m.title + ' 회의의 ' + coalesce(a.topic, '안건') + '에서 도출된 결정: ' + node.content AS graph_context
ORDER BY score DESC, node.created_at DESC
LIMIT 20"""


def _get_meeting_template() -> str:
    """Meeting 검색용 기본 템플릿 (m.date 제거됨, created_at 사용)"""
    return """MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)
WHERE u.name CONTAINS $entity_name
RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
       u.name + '님이 참여한 회의: ' + m.title AS graph_context
ORDER BY m.created_at DESC
LIMIT 20"""


def _get_user_team_template() -> str:
    """User 검색용 기본 템플릿"""
    return """MATCH (u:User {name: $entity_name})-[:MEMBER_OF]->(team:Team)
MATCH (team)<-[:MEMBER_OF]-(member:User)
WHERE member <> u AND (team)<-[:MEMBER_OF]-(:User {id: $user_id})
RETURN member.id AS id, member.name AS title, member.email AS content, 1.0 AS score,
       member.name + '님은 ' + team.name + ' 팀의 멤버 (같은 팀: ' + u.name + ')' AS graph_context
ORDER BY member.name ASC
LIMIT 20"""


def _apply_focus_fallback(
    cypher: str, strategy: dict, query_intent: dict
) -> Tuple[str, dict]:
    """Focus 기반 fallback 템플릿 적용."""
    focus = query_intent.get("search_focus")
    primary_entity = query_intent.get("primary_entity")

    template_map = {
        "Meeting": _get_meeting_template,
        "User": _get_user_team_template,
        "Decision": _get_fulltext_template,
    }
    # 템플릿 호출
    cypher_func = template_map.get(focus, _get_fulltext_template)
    cypher = cypher_func()

    if focus in FOCUS_RULES:
        strategy["reasoning"] = (
            f"품질 검증 실패 → {FOCUS_RULES[focus]['fallback_reason']}"
        )
    else:
        strategy["reasoning"] = "품질 검증 실패 → fulltext fallback"

    # Fallback 사용 시 검색어 설정
    if primary_entity:
        strategy["search_term"] = primary_entity

    return cypher, strategy


def _sanitize_generated_cypher(cypher: str) -> str:
    """LLM 생성 Cypher의 흔한 오류를 보정합니다."""
    # 주석 제거
    cypher = re.sub(r"//.*", "", cypher)

    # 존재하지 않는 속성/관계 수정
    cypher = re.sub(r":MADE_DECISION\b", "", cypher)
    cypher = re.sub(
        r"\b(a\.|agenda\.)title\b", "a.topic", cypher, flags=re.IGNORECASE
    )
    cypher = re.sub(r"\bm\.date\b", "m.created_at", cypher, flags=re.IGNORECASE)

    # OPTIONAL MATCH 제거
    cypher = re.sub(
        r"OPTIONAL MATCH\s*\(u:User\)\s*-\s*\[\s*\]\s*->\s*\(node\)\s*\n?",
        "",
        cypher,
        flags=re.IGNORECASE,
    )

    # 불필요한 coalesce 제거
    cypher = re.sub(
        r',\s*coalesce\(u\.name,\s*"[^"]*"\)\s+AS\s+\w+',
        "",
        cypher,
        flags=re.IGNORECASE,
    )

    # Markdown 및 세미콜론 정리
    cypher = cypher.replace("```cypher", "").replace("```", "").strip()
    cypher = cypher.replace(";", "")

    # ORDER BY score 정리
    upper = cypher.upper()
    if "ORDER BY" in upper:
        parts = re.split(r"ORDER BY", cypher, flags=re.IGNORECASE)
        pre_order = parts[0]
        post_order = "ORDER BY" + parts[1] if len(parts) > 1 else ""

        if re.search(
            r"ORDER BY\s+score\s+DESC,\s*created_at\s+DESC", post_order, re.IGNORECASE
        ):
            if not re.search(r"\bcreated_at\b", pre_order):
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


def _is_safe_cypher(cypher: str) -> bool:
    """LLM Cypher 안전성/호환성 검증."""
    upper = cypher.upper()

    forbidden_keywords = [
        "CREATE",
        "MERGE",
        "DELETE",
        "DETACH",
        "SET",
        "REMOVE",
        "DROP",
        "LOAD CSV",
    ]
    for keyword in forbidden_keywords:
        if re.search(rf"\b{keyword}\b", upper):
            return False

    if re.search(r"\bCALL\b", upper):
        if not re.search(
            r"CALL\s+db\.index\.fulltext\.queryNodes", cypher, re.IGNORECASE
        ):
            return False

    if re.search(r"\bUNION\b", upper):
        return False

    if re.search(r"\bextract\s*\(", cypher, re.IGNORECASE):
        return False

    if not re.search(r"\bgraph_context\b", cypher, re.IGNORECASE):
        return False

    return True


def _collect_cypher_issues(cypher: str, query_intent: dict) -> List[str]:
    if not cypher:
        return ["empty_cypher"]

    issues = _evaluate_cypher_quality(cypher)
    if not _is_safe_cypher(cypher):
        issues.append("unsafe_cypher")
    if not _is_intent_aligned(cypher, query_intent):
        issues.append("intent_mismatch")
    return issues


def _is_intent_aligned(cypher: str, query_intent: dict) -> bool:
    """LLM Cypher가 의도한 search_focus와 정합적인지 검사."""
    if not query_intent:
        return True

    focus = query_intent.get("search_focus")
    upper = cypher.upper()

    rules = FOCUS_RULES.get(focus)
    if not rules:
        return True

    required = rules["required"]
    forbidden = rules["forbidden"]

    if required and not any(token in upper for token in required):
        return False
    if forbidden and any(token in upper for token in forbidden):
        return False

    return True


def _format_cypher_feedback(issues: List[str], cypher: str) -> str:
    """LLM 재시도를 위한 피드백 생성."""
    issue_lines = ", ".join(issues)
    return (
        "다음 문제를 수정해서 Cypher를 다시 생성하세요."
        f"\n- 문제: {issue_lines}"
        "\n- 반드시 graph_context 포함 (문자열 조합 필수)"
        "\n- RETURN ... AS graph_context 형식 준수"
        "\n- 반드시 LIMIT 포함"
        "\n- 반드시 $user_id로 접근 제어 포함"
        "\n- $query 파라미터 사용 금지 (실제 값 사용)"
        f"\n현재 Cypher:\n{cypher}"
    )


async def _attempt_cypher_with_feedback(
    query: str,
    query_intent: dict,
    user_id: str,
    max_attempts: int = 3,
) -> str:
    """LLM Cypher 생성 재시도 루프."""
    feedback = None
    for attempt in range(1, max_attempts + 1):
        cypher = await _generate_text_to_cypher_raw(
            query, query_intent, user_id, feedback=feedback
        )
        issues = _collect_cypher_issues(cypher, query_intent)
        if not issues:
            logger.info(
                "[Text-to-Cypher] 생성 성공",
                extra={"attempt": attempt, "query": query},
            )
            return cypher

        feedback = _format_cypher_feedback(issues, cypher)
        logger.warning(
            "[Text-to-Cypher] 생성 실패, 재시도",
            extra={"attempt": attempt, "issues": issues},
        )

    return ""


async def _extract_subqueries(query: str) -> List[str]:
    """LLM 기반 쿼리 분해."""
    llm = get_cypher_generator_llm()
    system_prompt = textwrap.dedent(
        """너는 사용자의 질문을 독립적인 검색 질문으로 분해하는 시스템이다.

규칙:
1. JSON만 출력한다.
2. 키는 subqueries 하나만 사용한다.
3. subqueries는 문자열 배열이며, 1~3개로 제한한다.
4. 분해가 필요 없다면 원문 질문 하나만 넣는다.
"""
    ).strip()

    user_message = f"질문: {query}\n\nJSON으로만 응답:"

    try:
        content = ""
        async for chunk in llm.astream(
            [
                SystemMessage(system_prompt),
                HumanMessage(user_message),
            ]
        ):
            if hasattr(chunk, "content"):
                content += chunk.content
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"```(?:json)?\n?", "", content)
            content = content.strip("`").strip()

        data = json.loads(content)
        subqueries = data.get("subqueries")
        if isinstance(subqueries, list):
            cleaned = [
                q.strip() for q in subqueries if isinstance(q, str) and q.strip()
            ]
            if cleaned:
                return cleaned[:3]
    except Exception as e:
        logger.warning(
            "[Text-to-Cypher] 서브쿼리 분해 실패", extra={"error": str(e)}
        )

    return [query]


def _evaluate_cypher_quality(cypher: str) -> List[str]:
    """Cypher 품질 검증."""
    issues: List[str] = []
    upper = cypher.upper()

    if not any(keyword in upper for keyword in ["MATCH", "CALL"]):
        issues.append("missing_match_or_call")

    if "RETURN" not in upper:
        issues.append("missing_return")

    if "LIMIT" not in upper:
        issues.append("missing_limit")

    if not re.search(r"\bgraph_context\b", cypher, re.IGNORECASE):
        issues.append("missing_graph_context")

    if re.search(r"\bCALL\b", upper) and not re.search(
        r"CALL\s+db\.index\.fulltext\.queryNodes", cypher, re.IGNORECASE
    ):
        issues.append("unsupported_call")

    if re.search(r"\bSKIP\b", upper) and "LIMIT" not in upper:
        issues.append("skip_without_limit")

    return issues


def cypher_generator(state: MitSearchState) -> Dict[str, Any]:
    """동기 테스트용 래퍼."""
    return asyncio.run(cypher_generator_async(state))
