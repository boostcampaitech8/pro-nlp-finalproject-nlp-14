"""Template-based Cypher 생성 (조건부 절 조립 방식).

오버엔지니어링 방지: 복잡한 템플릿 엔진 대신 단순 함수로만 구현하되,
키워드($search_term)와 날짜($start_date) 조건이 누락되지 않도록 동적 조립.
"""

import logging

logger = logging.getLogger(__name__)


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
    if search_term and search_term.strip():
        # 제목이나 내용에 키워드가 포함되어야 함
        keyword_clause = "AND (target.title CONTAINS $search_term OR target.content CONTAINS $search_term)"
    # -------------------------------------------------------

    # Pattern 1: 특정 인물의 결정사항 (User -> Meeting -> Agenda -> Decision)
    if intent_type == "entity_search" and search_focus == "Decision" and primary_entity:
        cypher = f"""
        MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(target:Decision)
        WHERE u.name CONTAINS $entity_name
          AND (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
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
          AND (target)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
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

    # Pattern 3: 시간 기반 결정사항 (User -> Meeting ... -> Decision)
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
        logger.info(f"[Template] Pattern 3: Temporal Decision")
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
    
    # 기본 파라미터
    params = {
        "user_id": user_id,
        "search_term": search_term,  # 키워드 검색용 (있든 없든 전달)
    }
    
    # 엔티티 검색용
    if primary_entity:
        params["entity_name"] = primary_entity
    
    # 날짜 필터용
    if date_filter:
        if date_filter.get("start"):
            params["start_date"] = date_filter["start"]
        if date_filter.get("end"):
            params["end_date"] = date_filter["end"]
    
    return params