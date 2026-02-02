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
    keywords: list = None,
    user_id: str = None,
    date_filter: dict = None,
    search_term: str = None  # 하위 호환성을 위해 유지
) -> str | None:
    """단순 패턴을 위한 Template Cypher 생성.

    지원 패턴:
    1. Entity + Decision (옵션: 키워드, 날짜)
    2. Entity + Meeting (옵션: 키워드, 날짜)
    3. Temporal + Decision (옵션: 키워드)

    Args:
        keywords: 추가 검색 키워드 리스트 (primary_entity 제외)
        search_term: (deprecated) keywords 우선 사용

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

    # 키워드 검색 필터 (keywords 리스트 사용)
    keyword_clause = ""
    team_keyword_clause = ""

    # keywords 리스트를 search_term으로 변환 (첫 번째 키워드 사용)
    effective_search_term = None
    if keywords and len(keywords) > 0:
        effective_search_term = keywords[0]
    elif search_term:  # 하위 호환성
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
        # Decision 노드는 title이 없고 content만 있으므로, content만 검색
        keyword_clause_fixed = ""
        if effective_search_term and effective_search_term.strip():
            keyword_clause_fixed = "AND target.content CONTAINS $search_term"
        
        cypher = f"""
        MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(target:Decision)
        WHERE u.name CONTAINS $entity_name
          {date_clause}
          {keyword_clause_fixed}
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
        logger.info(f"[Template] Pattern 1: Entity Decision (Entity={primary_entity}, Keyword={bool(effective_search_term)})")
        return cypher.strip()

    # Pattern 2: 특정 인물의 회의 (User -> Meeting)
    if intent_type == "entity_search" and search_focus == "Meeting" and primary_entity:
        # Meeting 노드는 created_at 대신 scheduled_at 사용
        date_clause_meeting = ""
        if date_filter and date_filter.get("start") and date_filter.get("end"):
            date_clause_meeting = "AND target.scheduled_at >= datetime($start_date) AND target.scheduled_at <= datetime($end_date)"

        cypher = f"""
                MATCH (u:User)-[:PARTICIPATED_IN]->(target:Meeting)
                WHERE u.name CONTAINS $entity_name
                    {date_clause_meeting}
                    {keyword_clause}
        RETURN target.id AS id,
               target.title AS title,
               target.title AS content,
               target.status AS status,
               target.scheduled_at AS created_at,
               target.id AS meeting_id,
               target.title AS meeting_title,
               1.0 AS score,
               '회의: ' + target.title + ' (참여자: ' + u.name + ')' AS graph_context
        ORDER BY target.scheduled_at DESC
        LIMIT 20
        """
        logger.info(f"[Template] Pattern 2: Entity Meeting (Entity={primary_entity}, Keyword={bool(search_term)})")
        return cypher.strip()

    # Pattern 3: 사용자가 속한 팀 자체 검색 (Membership)
    if intent_type == "entity_search" and search_focus == "Membership" and primary_entity:
        cypher = f"""
        MATCH (u:User)-[:MEMBER_OF]->(team:Team)
        WHERE u.name CONTAINS $entity_name
        RETURN team.id AS id,
               team.name AS title,
               team.name AS content,
               1.0 AS score,
               u.name + '님이 속한 팀: ' + team.name AS graph_context
        ORDER BY team.name ASC
        LIMIT 20
        """
        logger.info(f"[Template] Pattern 3: Membership (User={primary_entity})")
        return cypher.strip()

    # Pattern 4: 팀원 검색 (팀 이름 또는 사용자 이름)
    if intent_type == "entity_search" and search_focus == "TeamMembers" and primary_entity:
        # 팀 이름 패턴 감지 (하이픈, "팀" 문자열 포함 등)
        is_team_name = "-" in primary_entity or "팀" in primary_entity or "Team" in primary_entity

        if is_team_name:
            # Pattern 4a: 팀 이름으로 직접 검색 (Team -> Members)
            cypher = f"""
            MATCH (team:Team)<-[:MEMBER_OF]-(member:User)
            WHERE team.name CONTAINS $entity_name
              {team_keyword_clause}
            RETURN member.id AS id,
                   member.name AS title,
                   member.email AS content,
                   1.0 AS score,
                   member.name + '님은 ' + team.name + ' 팀의 멤버' AS graph_context
            ORDER BY member.name ASC
            LIMIT 20
            """
            logger.info(f"[Template] Pattern 4a: TeamMembers by Team Name (Team={primary_entity})")
        else:
            # Pattern 4b: 사용자 이름으로 팀 찾기 (User -> Team -> Members)
            cypher = f"""
            MATCH (u:User)-[:MEMBER_OF]->(team:Team)<-[:MEMBER_OF]-(member:User)
            WHERE u.name CONTAINS $entity_name
              AND member.id <> u.id
              {team_keyword_clause}
            RETURN member.id AS id,
                   member.name AS title,
                   member.email AS content,
                   1.0 AS score,
                   member.name + '님은 ' + team.name + ' 팀의 멤버 (같은 팀: ' + u.name + ')' AS graph_context
            ORDER BY member.name ASC
            LIMIT 20
            """
            logger.info(f"[Template] Pattern 4b: TeamMembers by User Name (User={primary_entity})")

        return cypher.strip()

    # Pattern 5: 복합 메타 검색 (담당자와 같은 팀원)
    if intent_type == "meta_search" and search_focus == "Composite" and effective_search_term:
        cypher = f"""
        MATCH (m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)-[:TRIGGERS]->(ai:ActionItem)<-[:ASSIGNED_TO]-(owner:User)
        MATCH (owner)-[:MEMBER_OF]->(team:Team)<-[:MEMBER_OF]-(member:User)
        WHERE (ai.content CONTAINS $search_term OR a.topic CONTAINS $search_term OR m.title CONTAINS $search_term)
          AND member.id <> owner.id
        RETURN member.id AS id,
               member.name AS title,
               member.email AS content,
               1.0 AS score,
               member.name + '님은 ' + team.name + ' 팀의 멤버 (담당자: ' + owner.name + ')' AS graph_context
        ORDER BY member.name ASC
        LIMIT 20
        """
        logger.info("[Template] Pattern 5: Composite Team Members")
        return cypher.strip()

    # Pattern 6: 시간 기반 결정사항 (User -> Meeting ... -> Decision)
    # 주의: Temporal Search는 primary_entity가 없을 때 주로 사용됨
    if intent_type == "temporal_search" and search_focus == "Decision" and date_filter:
        # Decision 노드는 title이 없고 content만 있으므로, content만 검색
        keyword_clause_temporal = ""
        if effective_search_term and effective_search_term.strip():
            keyword_clause_temporal = "AND target.content CONTAINS $search_term"
        
        cypher = f"""
        MATCH (u:User {{id: $user_id}})-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(target:Decision)
        WHERE target.created_at >= datetime($start_date)
          AND target.created_at <= datetime($end_date)
          {keyword_clause_temporal}
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
        logger.info("[Template] Pattern 6: Temporal Decision")
        return cypher.strip()

    # 템플릿 없음
    logger.info(f"[Template] No template for: {intent_type} / {search_focus}")
    return None


def get_template_parameters(
    intent_type: str,
    primary_entity: str,
    keywords: list = None,
    user_id: str = None,
    date_filter: dict = None,
    search_term: str = None  # 하위 호환성
) -> dict:
    """Template Cypher용 파라미터 생성 (일관성 유지)."""

    # keywords 리스트를 search_term으로 변환
    final_search_term = ""
    if keywords and len(keywords) > 0:
        final_search_term = keywords[0]
    elif search_term:  # 하위 호환성
        final_search_term = search_term
        if intent_type == "entity_search" and primary_entity:
            final_search_term = _clean_search_term(search_term, primary_entity)

    # 기본 파라미터
    params = {
        "user_id": user_id or "",
        "search_term": final_search_term,  # 첫 번째 키워드 전달
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
