"""Neo4j 검색 실행을 위한 Tool retrieval 노드."""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List

from ..state import MitSearchState
from ..tools.search_tools import execute_cypher_search_async

logger = logging.getLogger(__name__)


def normalize_query(query: str) -> str:
    """쿼리를 정규화합니다: 메타키워드 → 동사 → 조사 순서로 제거.

    한글 처리 전략:
    1. 복합어 보호: "회의", "예산", "팀", "결정사항" 같은 명사는 먼저 보호
    2. 불필요한 동사/조사 제거
    3. 공백 정리 및 결과 반환
    """
    search_query = query.strip()

    # 단계 0: 보호해야할 한글 복합어 (동사 제거 전에 보호)
    protected_terms = {
        "결정사항": "__PROTECTED_DECISION__",
        "액션": "__PROTECTED_ACTION__",
        "액션아이템": "__PROTECTED_ACTION_ITEM__",
        "회의": "__PROTECTED_MEETING__",
        "예산": "__PROTECTED_BUDGET__",
        "팀": "__PROTECTED_TEAM__",
        "일정": "__PROTECTED_SCHEDULE__",
        "회의실": "__PROTECTED_ROOM__",
        "회고": "__PROTECTED_RETROSPECTIVE__",
    }
    keywords = search_query
    protected_map = {}
    for term, placeholder in protected_terms.items():
        if term in keywords:
            protected_map[placeholder] = term
            keywords = keywords.replace(term, placeholder)

    # 단계 1: 메타 키워드 제거 (보호된 용어는 제외)
    # "사항", "내용", "정보", "것", "거" 등 순수 메타 문구만 제거
    meta_keywords = ["사항", "내용", "정보", "것", "거"]
    for meta in meta_keywords:
        keywords = keywords.replace(meta, " ")

    # 단계 2: 동사/형용사 제거
    verbs_and_adjectives = [
        "있어", "있나", "있어요", "있습니까", "있습니다",
        "뭐야", "뭐지", "뭐냐", "뭐예요", "뭐네",
        "뭔지", "뭔데", "뭔데요",
        "할려고", "할거야", "할거냐", "할게",
        "되나", "되나요", "되지", "되네",
        "알려줘", "알려주세요", "알려줘요",
        "찾아줘", "찾아주세요", "찾아줘요",
        "보여줘", "보여주세요", "보여줄래",
        "하지", "하면서", "하면",
        "열렸어", "열렸나", "열렸어요",
        "나타내", "의미하", "표현하",
    ]
    for verb in verbs_and_adjectives:
        keywords = keywords.replace(verb, " ")

    # 단계 3: 조사/접속사 제거 (단어 경계 기준으로 정확히)
    stop_words = [
        "연결된", "관련된", "관련", "님", "에게", "과", "은", "는", "이", "가", "을", "를", "와", "랑",
        "나", "너", "그", "저", "그게", "뭐가", "뭐를", "뭐는",
        "?", "!", "야", "네", "어", "요", "언제", "어디", "누가", "누구"
    ]
    for stop_word in stop_words:
        # 단어 경계 기준으로 제거
        keywords = re.sub(r'\b' + re.escape(stop_word) + r'\b', ' ', keywords)

    # 보호된 용어 복원
    normalized = " ".join(keywords.split()).strip()
    for placeholder, original_term in protected_map.items():
        normalized = normalized.replace(placeholder, original_term)

    return normalized


def generate_cypher_by_strategy(
    strategy: str,
    query_intent: Dict[str, Any],
    entity_types: List[str],
    normalized_keywords: str,
    filters: Dict[str, Any],
    cypher_template: str,
) -> str:
    """선택된 전략에 따라 Cypher 쿼리를 생성합니다."""
    date_filter = ""
    if filters.get("date_range"):
        date_filter = " AND n.created_at >= datetime($start_date) AND n.created_at <= datetime($end_date)"

    if strategy == "team_member_search":
        # 팀원 검색: 같은 팀의 사람들을 찾음
        cypher = f"""MATCH (u:User)-[:MEMBER_OF]->(t:Team)<-[:MEMBER_OF]-(team_member:User)
WHERE u.name CONTAINS $query AND (t)<-[:MEMBER_OF]-(:User {{id: $user_id}})
{date_filter}
RETURN team_member.id AS id, team_member.name AS title, team_member.name AS content, "active" AS status, t.created_at AS created_at, t.id AS team_id, t.name AS team_name, 1.0 AS score,
       team_member.name + '님은 ' + t.name + ' 팀의 멤버입니다.' AS graph_context
ORDER BY team_member.name ASC
LIMIT 20"""
        return cypher

    elif strategy == "user_search":
        cypher = f"""MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)
WHERE u.name CONTAINS $query
{date_filter}
RETURN d.id AS id, d.content AS content, d.status AS status, d.created_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, 1.0 AS score,
       u.name + '님이 참여한 ' + m.title + ' 회의의 ' + a.topic + ' 안건에서 도출된 결정사항: ' + d.content AS graph_context
ORDER BY d.created_at DESC
LIMIT 20"""
        return cypher

    elif strategy == "meeting_search":
        # Meeting 검색: 특정 인물($entity_name)이 있다면 그 사람과 함께한 회의 + 키워드 검색
        # Meeting 노드는 scheduled_at 필드 사용
        # date_filter를 scheduled_at으로 변경
        date_filter_meeting = ""
        if filters.get("date_range"):
            date_filter_meeting = " AND m.scheduled_at >= datetime($start_date) AND m.scheduled_at <= datetime($end_date)"

        cypher = f"""MATCH (target:User)-[:PARTICIPATED_IN]->(m:Meeting)
WHERE ($entity_name IS NULL OR $entity_name = '' OR target.name CONTAINS $entity_name)
  AND ($query = "*" OR m.title CONTAINS $query OR m.description CONTAINS $query OR m.summary CONTAINS $query)
{date_filter_meeting}
RETURN m.id AS id, m.title AS title, m.title AS content, m.status AS status,
       m.scheduled_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, 1.0 AS score,
       '회의: ' + m.title + ' (참여자: ' + target.name + ')' AS graph_context
ORDER BY m.scheduled_at DESC
LIMIT 20"""
        return cypher

    elif strategy == "agenda_search":
        cypher = f"""MATCH (u:User {{id: $user_id}})-[:PARTICIPATED_IN]->(m:Meeting)
MATCH (m)-[:CONTAINS]->(a:Agenda)
WHERE ($query = "*" OR a.topic CONTAINS $query OR a.description CONTAINS $query)
{date_filter}
RETURN a.id AS id, a.topic AS title, coalesce(a.description, a.topic) AS content,
       m.status AS status, a.created_at AS created_at,
       m.id AS meeting_id, m.title AS meeting_title, 1.0 AS score,
       m.title + ' 회의의 안건: ' + a.topic AS graph_context
ORDER BY a.created_at DESC
LIMIT 20"""
        return cypher

    elif strategy == "action_search":
        # Action Item 검색: 내용으로 검색하고 담당자(assignee) 정보 포함
        # 관계: User -[:ASSIGNED_TO]-> ActionItem
        cypher = f"""MATCH (ai:ActionItem)
WHERE ($query = "*" OR ai.content CONTAINS $query)
{date_filter}
OPTIONAL MATCH (u:User)-[:ASSIGNED_TO]->(ai)
RETURN ai.id AS id, ai.content AS title, ai.content AS content, ai.status AS status,
       CASE WHEN ai.due_date IS NOT NULL THEN ai.due_date ELSE null END AS created_at,
       coalesce(u.name, "미배정") AS assignee, u.id AS assignee_id, 1.0 AS score,
       'Action Item: ' + ai.content + ' (담당자: ' + coalesce(u.name, '미배정') + ', 상태: ' + ai.status + ')' AS graph_context
ORDER BY ai.due_date DESC
LIMIT 20"""
        return cypher

    elif strategy == "action_with_team_search":
        # 복합 검색: Action Item 담당자 + 그 담당자의 팀원
        # Multi-hop: User -[:ASSIGNED_TO]-> ActionItem, User -[:MEMBER_OF]-> Team <-[:MEMBER_OF]- User
        cypher = f"""MATCH (ai:ActionItem)
WHERE ($query = "*" OR ai.content CONTAINS $query)
{date_filter}
OPTIONAL MATCH (u:User)-[:ASSIGNED_TO]->(ai)
OPTIONAL MATCH (u)-[:MEMBER_OF]->(t:Team)<-[:MEMBER_OF]-(team_member:User)
WHERE team_member <> u
RETURN DISTINCT ai.id AS action_id, ai.content AS action_title, coalesce(u.name, "미배정") AS assignee,
       team_member.id AS team_member_id, team_member.name AS team_member_name,
       t.name AS team_name, u.id AS assignee_id, 1.0 AS score
ORDER BY ai.due_date DESC, team_member.name ASC
LIMIT 50"""
        return cypher

    elif strategy == "composite_search":
        # 복합 검색: Decision → ActionItem → 담당자 → 팀원까지 한 번에
        # 관계: Agenda -[:HAS_DECISION]-> Decision -[:TRIGGERS]-> ActionItem <-[:ASSIGNED_TO]- User
        cypher = f"""MATCH (m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)
WHERE ($query = "*" OR d.content CONTAINS $query OR d.context CONTAINS $query)
{date_filter}
OPTIONAL MATCH (d)-[:TRIGGERS]->(ai:ActionItem)
OPTIONAL MATCH (assignee:User)-[:ASSIGNED_TO]->(ai)
OPTIONAL MATCH (assignee)-[:MEMBER_OF]->(team:Team)<-[:MEMBER_OF]-(teammate:User)
WHERE teammate <> assignee
RETURN DISTINCT
    d.id AS decision_id,
    d.content AS decision_content,
    ai.id AS action_id,
    ai.content AS action_title,
    assignee.name AS assignee_name,
    assignee.id AS assignee_id,
    teammate.id AS teammate_id,
    teammate.name AS teammate_name,
    team.name AS team_name,
    1.0 AS score,
    d.created_at AS created_at
ORDER BY d.created_at DESC
LIMIT 50"""
        return cypher

    elif strategy == "text_to_cypher":
        # LLM이 생성한 Cypher를 그대로 사용
        return cypher_template

    else:  # "fulltext_search"
        cypher = re.sub(
            r"CALL db\.index\.fulltext\.queryNodes\(\'decision_search\',\s*[\"']([^\"']*)[\"']?\)",
            "CALL db.index.fulltext.queryNodes('decision_search', $query)",
            cypher_template,
        )
        return cypher


async def tool_executor_async(state: MitSearchState) -> Dict[str, Any]:
    """Neo4j에 대해 생성된 Cypher 쿼리를 실행.

    Contract:
        reads: mit_search_cypher, mit_search_strategy, mit_search_query_intent, user_id
        writes: mit_search_raw_results, mit_search_fallback_used
    """
    
    exec_start = time.time()
    logger.info("[Tool Executor] 시작")

    try:
        cypher = state.get("mit_search_cypher", "")
        strategy = state.get("mit_search_strategy", {})
        intent = state.get("mit_search_query_intent", {})
        user_id = state.get("user_id", "")

        # filters는 query_intent에서 추출 (일관성 유지)
        filters = {
            "date_range": intent.get("date_range"),
            "entity_types": intent.get("entity_types"),
        }

        if not cypher:
            logger.warning("[Tool Executor] Cypher 쿼리 없음")
            return {"mit_search_raw_results": []}

        # [수정] 파라미터 준비: query + user_id + entity_name(Intent에서 추출)
        primary_entity = intent.get("primary_entity", "")

        # ✅ keywords 우선 사용 (Intent 분석 결과), 없으면 strategy의 search_term 사용
        keywords = intent.get("keywords", [])
        search_term_value = keywords[0] if keywords else strategy.get("search_term", "")

        parameters = {
            "user_id": user_id,
            "query": search_term_value,
            "search_term": search_term_value,  # [CRITICAL] Template Cypher 호환성
            "keyword": search_term_value,
            "entity_name": primary_entity,
            "primary_entity": primary_entity,
            "entity": primary_entity,
            "name": primary_entity,
            "target_name": primary_entity,
        }
        
        # 시간 필터 파라미터 추가
        date_range = filters.get("date_range")
        if date_range:
            parameters["start_date"] = date_range.get("start")
            parameters["end_date"] = date_range.get("end")

        logger.info(f"[Tool Executor] 실행 중: {strategy.get('strategy')} (검색어: {strategy.get('search_term')})")
        logger.info(f"[Tool Executor] 파라미터: {parameters}")
        
        # 실행 정보 출력
        print(f"\n[Cypher 실행] 전략: {strategy.get('strategy')}")
        print(f"[파라미터] query='{parameters.get('query')}', entity='{parameters.get('entity_name')}', user_id='{parameters.get('user_id')}'")
        
        # Cypher 실행 (비동기)
        db_start = time.time()
        results = await execute_cypher_search_async(
            cypher_query=cypher,
            parameters=parameters
        )
        total_time = (time.time() - exec_start) * 1000

        # Text-to-Cypher 결과가 없으면 entity_search 기반 fallback 시도
        fallback_used = False
        if not results and strategy.get("strategy") == "text_to_cypher":
            primary_entity = intent.get("primary_entity")

            if primary_entity:
                # Fallback 전략 수립
                fallback_strategy = {
                    "strategy": "user_search", # 기본적으로 user_search로 회귀하거나 meeting_search로 회귀
                    "search_term": primary_entity,
                    "reasoning": "text_to_cypher 결과 없음 → entity fallback",
                }
                
                # 상황에 맞는 템플릿 선택 (Meeting Focus라면 meeting_search 사용)
                target_strategy = "meeting_search" if intent.get("search_focus") == "Meeting" else "user_search"
                
                fallback_cypher = generate_cypher_by_strategy(
                    strategy=target_strategy,
                    query_intent=intent,
                    entity_types=filters.get("entity_types", []),
                    normalized_keywords=primary_entity,
                    filters=filters,
                    cypher_template="",
                )

                logger.info(
                    f"[Tool Executor] fallback 실행: {target_strategy}",
                    extra={"primary_entity": primary_entity},
                )

                # Fallback 파라미터 설정
                fallback_params = {
                    "query": primary_entity, # Fallback은 엔티티 이름으로 검색
                    "entity_name": primary_entity,
                    "user_id": user_id
                }
                if date_range:
                    fallback_params["start_date"] = date_range.get("start")
                    fallback_params["end_date"] = date_range.get("end")

                results = await execute_cypher_search_async(
                    cypher_query=fallback_cypher,
                    parameters=fallback_params,
                )
                fallback_used = True

                print(f"\n[신뢰도 조정] Fallback 사용 감지 → 신뢰도 패널티 적용")
                logger.info("[Tool Executor] Fallback 사용으로 신뢰도 패널티 적용")

        logger.info(f"[Tool Executor] 완료: {len(results)}개 결과 반환 ({total_time:.0f}ms)", extra={
            "count": len(results),
            "fallback_used": fallback_used,
        })

        return {
            "mit_search_raw_results": results,
            "mit_search_fallback_used": fallback_used,
        }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return {"mit_search_raw_results": []}


def tool_executor(state: MitSearchState) -> Dict[str, Any]:
    """동기 테스트용 래퍼."""
    return asyncio.run(tool_executor_async(state))
