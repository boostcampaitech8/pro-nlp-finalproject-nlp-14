"""전략 기반 Cypher 쿼리 생성 노드."""

import asyncio
import json
import logging
import re
import textwrap
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.graph.integration.llm import get_cypher_generator_llm

from ..nodes.tool_retrieval import _generate_cypher_by_strategy, _normalize_query
from ..state import MitSearchState
from ..utils.search_strategy_router import SearchStrategyRouter

logger = logging.getLogger(__name__)

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
    """LLM을 사용하여 자연어 쿼리를 Neo4j Cypher로 변환.

    Args:
        query: 자연어 검색 쿼리
        query_intent: 쿼리 의도 분석 결과
        user_id: 사용자 ID

    Returns:
        생성된 Cypher 쿼리 또는 빈 문자열 (실패 시)
    """
    llm = get_cypher_generator_llm()

    schema_info = textwrap.dedent(
        """
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
    ).strip()

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

    feedback_block = ""
    if feedback:
        feedback_block = f"\n\n수정 지침:\n{feedback}\n"

    system_prompt = textwrap.dedent(
        f"""당신은 Neo4j Cypher 쿼리 생성 전문가입니다.
스키마와 관계를 바탕으로 자연어 질문을 Neo4j Cypher 쿼리로 변환하세요.

{schema_info}

규칙:

1. 오직 Cypher 쿼리만 반환 (설명 없음)
2. **중요**: 존재하지 않는 관계/속성 사용 금지 (예: MADE_DECISION, Agenda.order, Meeting.date)
3. **필수**: RETURN 절에 반드시 'graph_context' 필드를 포함하여 그래프 관계를 문장화하세요.
   - graph_context는 노드 간 관계를 자연어로 표현한 것입니다.
   - 예: "김철수님이 참여한 예산회의의 마케팅 예산 안건에서 도출된 결정사항: 5천만원 승인"

현재 쿼리 의도 (반드시 이를 따르세요):
- Intent: {intent_type}
- Focus: {search_focus or "일반"}
- Entity: {primary_entity or "없음"}

**CRITICAL 지시 - Intent별 필수 구조**:

IF Intent = "entity_search" AND primary_entity = "{primary_entity}":
  → MATCH (u:User {{name: $query}})를 시작점으로 사용하세요
  IF search_focus = "Meeting": u → Meeting 검색
  IF search_focus = "Decision": u → Meeting → Agenda → Decision 검색
  IF search_focus = "User": u → Team → 다른 User 검색

IF Intent = "general_search":
  → FULLTEXT 검색으로 시작하세요 (CALL db.index.fulltext.queryNodes)

모든 경우:
    → WHERE 절에 반드시 사용자 접근 제어 포함: (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
    → 모든 Cypher는 LIMIT로 끝나야 함 (보통 20)
    → graph_context는 자연어 설명 필수

**중요**: 같은 Intent와 Focus가 주어지면 항상 같은 구조의 Cypher를 생성하세요!

**필수 요건**:
1. RETURN 절 포함
2. LIMIT 포함
3. graph_context 포함
4. $user_id 접근제어 포함 (WHERE 절 마지막)

=== 예시1 ===
질문: "신수효가 참가한 회의 뭐가 있어?"
의도: entity_search + Meeting (primary_entity="신수효")
명령: primary_entity를 WHERE 절에서 필터링하세요!
Cypher:
MATCH (u:User {{name: $query}})-[:PARTICIPATED_IN]->(m:Meeting)
WHERE (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
       u.name + '님이 참여한 회의: ' + m.title AS graph_context
ORDER BY m.created_at DESC LIMIT 20

=== 예시2 ===
질문: "신수효 관련 결정사항"
의도: entity_search + Decision (primary_entity="신수효")
명령: 사람을 통해 회의→안건→결정으로 이동하되, WHERE 절에서 사람과 사용자 모두 검증!
Cypher:
MATCH (u:User {{name: $query}})-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)
WHERE (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
RETURN d.id AS id, d.content AS content, d.status AS status, 1.0 AS score,
       u.name + '님이 참여한 ' + m.title + ' 회의의 결정: ' + d.content AS graph_context
ORDER BY d.created_at DESC LIMIT 20

=== 예시3 ===
질문: "교육 프로그램에 대한 결정사항"
의도: general_search + Decision (no primary_entity)
명령: FULLTEXT 검색으로 결정사항을 찾되, 사용자가 참여한 회의만 포함!
Cypher:
CALL db.index.fulltext.queryNodes('decision_search', $query) YIELD node, score
MATCH (a:Agenda)-[:HAS_DECISION]->(node)
MATCH (m:Meeting)-[:CONTAINS]->(a)
WHERE (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
RETURN node.id AS id, node.content AS content, node.status AS status, score,
       m.title + ' 회의의 ' + coalesce(a.title, '안건') + '에서의 결정: ' + node.content AS graph_context
ORDER BY score DESC LIMIT 20

=== 예시4 ===
질문: "신수효와 같은 팀원은?"
의도: entity_search + User (primary_entity="신수효", search_focus="User")
명령: 사람을 찾으면, 그 사람의 팀을 거쳐 다른 팀원들을 찾으세요!
Cypher:
MATCH (u:User {{name: $query}})-[:MEMBER_OF]->(team:Team)
MATCH (team)<-[:MEMBER_OF]-(member:User)
WHERE member <> u AND (team)<-[:MEMBER_OF]-(:User {{id: $user_id}})
RETURN member.id AS id, member.name AS title, member.email AS content, 1.0 AS score,
       member.name + '님은 ' + team.name + ' 팀의 멤버 (같은 팀: ' + u.name + ')' AS graph_context
ORDER BY member.name ASC LIMIT 20
{feedback_block}
"""
    ).strip()

    user_message = f"질문: {query}\n\nCypher 쿼리를 생성하세요:"

    try:
        cypher = ""
        async for chunk in llm.astream([
            SystemMessage(system_prompt),
            HumanMessage(user_message),
        ]):
            if hasattr(chunk, 'content'):
                cypher += chunk.content
                print(chunk.content, end="", flush=True)
        print()  # 줄바꿈
        cypher = cypher.strip()

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

        # 콘솔에 생성된 Cypher 출력
        print(f"\n{'='*80}")
        print("[LLM 생성 Cypher]")
        print(f"{'='*80}")
        print(cypher)
        print(f"{'='*80}\n")

        return cypher
    except Exception as e:
        logger.error(f"[Text-to-Cypher] 생성 실패: {e}")
        return ""


async def _generate_text_to_cypher(query: str, query_intent: dict, user_id: str) -> str:
    """LLM Cypher 생성 + 품질/안전성 피드백 기반 재시도.

    복합 질문은 LLM 기반 분해 후 각 서브쿼리에 대해 생성 시도합니다.
    """
    subqueries = await _extract_subqueries(query)
    logger.info(
        "[Text-to-Cypher] 서브쿼리 분해 완료",
        extra={"count": len(subqueries), "subqueries": subqueries},
    )
    for subquery in subqueries:
        cypher = await _attempt_cypher_with_feedback(subquery, query_intent, user_id)
        if cypher:
            return cypher

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

        # LLM 우선 생성 (룰베이스 최소화)
        llm_cypher = await _generate_text_to_cypher(query, query_intent, user_id)
        if llm_cypher:
            strategy = {
                "strategy": "text_to_cypher",
                "search_term": normalized_keywords,
                "reasoning": "LLM 우선 생성",
            }
            logger.info(
                "[Cypher Generator] LLM Cypher 사용",
                extra={"strategy": strategy["strategy"], "search_term": strategy["search_term"]},
            )
            return {"mit_search_cypher": llm_cypher, "mit_search_strategy": strategy}

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
                cypher, strategy = _apply_focus_fallback(cypher, strategy, query_intent)
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

        quality_issues = _collect_cypher_issues(cypher, query_intent)
        if quality_issues:
            logger.warning(
                "[Cypher Generator] 품질/의도 검증 실패, LLM 재생성 시도",
                extra={"issues": quality_issues},
            )
            if strategy.get("strategy") == "text_to_cypher":
                repaired = await _attempt_cypher_with_feedback(query, query_intent, user_id)
                if repaired:
                    cypher = repaired
                    strategy["reasoning"] = "품질/의도 이슈 → LLM 재생성"
                else:
                    cypher, strategy = _apply_focus_fallback(cypher, strategy, query_intent)
            else:
                cypher, strategy = _apply_focus_fallback(cypher, strategy, query_intent)

        logger.info(f"Generated Cypher ({len(cypher)} chars)")
        logger.debug(f"Generated Cypher:\n{cypher}")

        # 생성된 Cypher를 콘솔에 출력
        print(f"\n{'='*80}")
        print(f"[최종 실행 Cypher] (전략: {strategy['strategy']})")
        print(f"{'='*80}")
        print(cypher)
        print(f"{'='*80}\n")

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
RETURN node.id AS id, node.content AS content, node.status AS status, node.created_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, score,
       m.title + ' 회의의 ' + coalesce(a.title, '안건') + '에서 도출된 결정: ' + node.content AS graph_context
ORDER BY score DESC, node.created_at DESC
LIMIT 20"""


def _get_meeting_template() -> str:
    """Meeting 검색용 기본 템플릿 (사람 참여 기준)"""
    return """MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)
WHERE u.name CONTAINS $query
  AND (m)<-[:PARTICIPATED_IN]-(:User {id: $user_id})
RETURN m.id AS id, m.title AS title, m.created_at AS created_at, 1.0 AS score,
       u.name + '님이 참여한 회의: ' + m.title AS graph_context
ORDER BY m.created_at DESC
LIMIT 20"""


def _get_user_team_template() -> str:
    """User 검색용 기본 템플릿 (같은 팀원)"""
    return """MATCH (u:User {name: $query})-[:MEMBER_OF]->(team:Team)
MATCH (team)<-[:MEMBER_OF]-(member:User)
WHERE member <> u AND (team)<-[:MEMBER_OF]-(:User {id: $user_id})
RETURN member.id AS id, member.name AS title, member.email AS content, 1.0 AS score,
       member.name + '님은 ' + team.name + ' 팀의 멤버 (같은 팀: ' + u.name + ')' AS graph_context
ORDER BY member.name ASC
LIMIT 20"""


def _apply_focus_fallback(cypher: str, strategy: dict, query_intent: dict) -> tuple[str, dict]:
    """Focus 기반 fallback 템플릿 적용."""
    focus = query_intent.get("search_focus")
    primary_entity = query_intent.get("primary_entity")

    template_map = {
        "Meeting": _get_meeting_template,
        "User": _get_user_team_template,
        "Decision": _get_fulltext_template,
    }
    cypher = template_map.get(focus, _get_fulltext_template)()

    if focus in FOCUS_RULES:
        strategy["reasoning"] = f"품질 검증 실패 → {FOCUS_RULES[focus]['fallback_reason']}"
    else:
        strategy["reasoning"] = "품질 검증 실패 → fulltext fallback"

    if primary_entity:
        strategy["search_term"] = primary_entity

    return cypher, strategy


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


def _is_safe_cypher(cypher: str) -> bool:
    """LLM Cypher 안전성/호환성 검증.

    - 쓰기 작업 차단
    - 허용되지 않은 CALL 차단
    - 지원하지 않는 함수 차단 (extract 등)
    - graph_context 반환 필수
    """
    upper = cypher.upper()

    # 쓰기/위험 키워드 차단
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

    # CALL 제한 (fulltext만 허용)
    if re.search(r"\bCALL\b", upper):
        if not re.search(r"CALL\s+db\.index\.fulltext\.queryNodes", cypher, re.IGNORECASE):
            return False

    # 지원하지 않는 함수 차단
    if re.search(r"\bextract\s*\(", cypher, re.IGNORECASE):
        return False

    # graph_context 반환 필수
    if not re.search(r"\bgraph_context\b", cypher, re.IGNORECASE):
        return False

    return True


def _collect_cypher_issues(cypher: str, query_intent: dict) -> list[str]:
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


def _format_cypher_feedback(issues: list[str], cypher: str) -> str:
    """LLM 재시도를 위한 피드백 생성."""
    issue_lines = ", ".join(issues)
    return (
        "다음 문제를 수정해서 Cypher를 다시 생성하세요."
        f"\n- 문제: {issue_lines}"
        "\n- 반드시 graph_context 포함"
        "\n- 반드시 RETURN 절 포함"
        "\n- 반드시 LIMIT 포함"
        "\n- 반드시 $user_id로 접근 제어 포함"
        "\n- 허용된 스키마/관계만 사용"
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
        cypher = await _generate_text_to_cypher_raw(query, query_intent, user_id, feedback=feedback)
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


async def _extract_subqueries(query: str) -> list[str]:
    """LLM 기반 쿼리 분해.

    반환은 1~3개의 서브쿼리로 제한합니다.
    """
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
        async for chunk in llm.astream([
            SystemMessage(system_prompt),
            HumanMessage(user_message),
        ]):
            if hasattr(chunk, 'content'):
                content += chunk.content
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"```(?:json)?\n?", "", content)
            content = content.strip("`").strip()

        data = json.loads(content)
        subqueries = data.get("subqueries")
        if isinstance(subqueries, list):
            cleaned = [q.strip() for q in subqueries if isinstance(q, str) and q.strip()]
            if cleaned:
                return cleaned[:3]
    except Exception as e:
        logger.warning("[Text-to-Cypher] 서브쿼리 분해 실패", extra={"error": str(e)})

    return [query]


def _evaluate_cypher_quality(cypher: str) -> list[str]:
    """Cypher 품질 검증.

    필수 기준을 충족하지 않으면 이슈 목록을 반환합니다.
    """
    issues: list[str] = []
    upper = cypher.upper()

    if not any(keyword in upper for keyword in ["MATCH", "CALL"]):
        issues.append("missing_match_or_call")

    if "RETURN" not in upper:
        issues.append("missing_return")

    if "LIMIT" not in upper:
        issues.append("missing_limit")

    if not re.search(r"\bgraph_context\b", cypher, re.IGNORECASE):
        issues.append("missing_graph_context")

    if not re.search(r"\$user_id\b", cypher):
        issues.append("missing_user_scope")

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
