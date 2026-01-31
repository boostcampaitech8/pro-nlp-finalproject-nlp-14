"""Template-based Cypher 생성 (조건부 절 조립 방식).

오버엔지니어링 방지: 복잡한 템플릿 엔진 대신 단순 함수로만 구현하되,
키워드($search_term)와 날짜($start_date) 조건이 누락되지 않도록 동적 조립.
"""

import logging

logger = logging.getLogger(__name__)


def _clean_search_term(search_term: str, entity: str) -> str:
    """검색어에서 엔티티 이름을 제거하여 순수 키워드만 남김.

    예: "신수효 회고" + entity="신수효" -> "회고"
    """
    if not search_term or not entity:
        return search_term
    return search_term.replace(entity, "").strip()


def generate_template_cypher(
    intent_type: str,
    search_focus: str,
    primary_entity: str,
    search_term: str,
    user_id: str,
    date_filter: dict = None
) -> str | None:
    """단순 패턴을 위한 Template Cypher 생성.

    지원 패턴:
    1. Entity + Decision (옵션: 키워드, 날짜)
    2. Entity + Meeting (옵션: 키워드, 날짜)
    3. Temporal + Decision (옵션: 키워드)

    Returns:
        Cypher 쿼리 또는 None (템플릿 없음)
    """

    # 1. 공통 조건절 조립 (Clause Builder)
    # -------------------------------------------------------
    # 날짜 필터 (모든 패턴에 공통 적용 가능)
    date_clause = ""
    if date_filter and date_filter.get("start") and date_filter.get("end"):
        # n은 쿼리 본문에서 대상 노드(Meeting 또는 Decision)로 alias 되어야 함
        date_clause = "AND target.created_at >= datetime($start_date) AND target.created_at <= datetime($end_date)"

    # 키워드 검색 필터 (엔티티 외에 추가 검색어가 있을 경우)
    keyword_clause = ""
    team_keyword_clause = ""

    # [CRITICAL FIX] entity_search인 경우 검색어에서 엔티티를 제거한 순수 키워드만 사용
    effective_search_term = search_term
    if intent_type == "entity_search" and primary_entity:
        effective_search_term = _clean_search_term(search_term, primary_entity)

    if effective_search_term and effective_search_term.strip():
        # 제목이나 내용에 키워드가 포함되어야 함
        keyword_clause = "AND (target.title CONTAINS $search_term OR target.content CONTAINS $search_term)"
        team_keyword_clause = "AND (member.name CONTAINS $search_term OR member.email CONTAINS $search_term)"
    # -------------------------------------------------------

    # Pattern 1: 특정 인물의 결정사항 (User -> Meeting -> Agenda -> Decision)
    if intent_type == "entity_search" and search_focus == "Decision" and primary_entity:
        cypher = f"""
        MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(target:Decision)
        WHERE u.name CONTAINS $entity_name
          {date_clause}
          {keyword_clause}
        RETURN target.id AS id,
               target.content AS content,
               target.status AS status,
               target.created_at AS created_at,
               m.id AS meeting_id,
               m.title AS meeting_title,
               1.0 AS score,
               u.name + '님이 참여한 ' + m.title + ' 회의의 결정사항: ' + target.content AS graph_context
        ORDER BY target.created_at DESC
        LIMIT 20
        """
        logger.info(f"[Template] Pattern 1: Entity Decision (Entity={primary_entity}, Keyword={bool(search_term)})")
        return cypher.strip()

    # Pattern 2: 특정 인물의 회의 (User -> Meeting)
    if intent_type == "entity_search" and search_focus == "Meeting" and primary_entity:
        cypher = f"""
                MATCH (u:User)-[:PARTICIPATED_IN]->(target:Meeting)
                WHERE u.name CONTAINS $entity_name
                    {date_clause}
                    {keyword_clause}
        RETURN target.id AS id,
               target.title AS title,
               target.title AS content,
               target.status AS status,
               target.created_at AS created_at,
               target.id AS meeting_id,
               target.title AS meeting_title,
               1.0 AS score,
               '회의: ' + target.title + ' (참여자: ' + u.name + ')' AS graph_context
        ORDER BY target.created_at DESC
        LIMIT 20
        """
        logger.info(f"[Template] Pattern 2: Entity Meeting (Entity={primary_entity}, Keyword={bool(search_term)})")
        return cypher.strip()

    # Pattern 3: 특정 인물의 팀원 (User -> Team -> Members)
    if intent_type == "entity_search" and search_focus == "Team" and primary_entity:
        cypher = f"""
        MATCH (u:User)-[:MEMBER_OF]->(team:Team)<-[:MEMBER_OF]-(member:User)
        WHERE u.name CONTAINS $entity_name
          AND member.id <> u.id
          AND (team)<-[:MEMBER_OF]-(:User {{id: $user_id}})
          {team_keyword_clause}
        RETURN member.id AS id,
               member.name AS title,
               member.email AS content,
               1.0 AS score,
               member.name + '님은 ' + team.name + ' 팀의 멤버 (같은 팀: ' + u.name + ')' AS graph_context
        ORDER BY member.name ASC
        LIMIT 20
        """
        logger.info(f"[Template] Pattern 3: Entity Team (Entity={primary_entity}, Keyword={bool(search_term)})")
        return cypher.strip()

        # Pattern 4: 복합 메타 검색 (담당자와 같은 팀원)
        if intent_type == "meta_search" and search_focus == "Composite" and search_term:
                cypher = """
                MATCH (m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_ACTION]->(ai:ActionItem)<-[:ASSIGNED_TO]-(owner:User)
                MATCH (owner)-[:MEMBER_OF]->(team:Team)<-[:MEMBER_OF]-(member:User)
                WHERE (ai.title CONTAINS $search_term OR a.title CONTAINS $search_term OR m.title CONTAINS $search_term)
                    AND member.id <> owner.id
                    AND (team)<-[:MEMBER_OF]-(:User {{id: $user_id}})
                RETURN member.id AS id,
                             member.name AS title,
                             member.email AS content,
                             1.0 AS score,
                             member.name + '님은 ' + team.name + ' 팀의 멤버 (담당자: ' + owner.name + ')' AS graph_context
                ORDER BY member.name ASC
                LIMIT 20
                """
                logger.info("[Template] Pattern 4: Composite Team Members")
                return cypher.strip()

        # Pattern 5: 시간 기반 결정사항 (User -> Meeting ... -> Decision)
    # 주의: Temporal Search는 primary_entity가 없을 때 주로 사용됨
    if intent_type == "temporal_search" and search_focus == "Decision" and date_filter:
        cypher = f"""
        MATCH (u:User {{id: $user_id}})-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(target:Decision)
        WHERE target.created_at >= datetime($start_date)
          AND target.created_at <= datetime($end_date)
          {keyword_clause}
        RETURN target.id AS id,
               target.content AS content,
               target.status AS status,
               target.created_at AS created_at,
               m.id AS meeting_id,
               m.title AS meeting_title,
               1.0 AS score,
               m.title + ' 회의의 결정사항: ' + target.content AS graph_context
        ORDER BY target.created_at DESC
        LIMIT 20
        """
        logger.info("[Template] Pattern 5: Temporal Decision")
        return cypher.strip()

    # 템플릿 없음
    logger.info(f"[Template] No template for: {intent_type} / {search_focus}")
    return None


def get_template_parameters(
    intent_type: str,
    primary_entity: str,
    search_term: str,
    user_id: str,
    date_filter: dict = None
) -> dict:
    """Template Cypher용 파라미터 생성 (일관성 유지)."""

    # [CRITICAL FIX] entity_search인 경우 검색어에서 엔티티를 제거한 순수 키워드만 사용
    final_search_term = search_term
    if intent_type == "entity_search" and primary_entity:
        final_search_term = _clean_search_term(search_term, primary_entity)

    # 기본 파라미터
    params = {
        "user_id": user_id,
        "search_term": final_search_term,  # 정제된 키워드 전달
    }

    # 엔티티 검색용
    if primary_entity:
        params["entity_name"] = primary_entity
        params["primary_entity"] = primary_entity
        params["entity"] = primary_entity
        params["name"] = primary_entity

    # 날짜 필터용
    if date_filter:
        if date_filter.get("start"):
            params["start_date"] = date_filter["start"]
        if date_filter.get("end"):
            params["end_date"] = date_filter["end"]

    return params
