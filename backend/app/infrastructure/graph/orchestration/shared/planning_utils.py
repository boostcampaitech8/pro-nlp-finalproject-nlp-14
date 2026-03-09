"""Shared Planning Utilities for Orchestration"""

PLANNING_MAX_RETRY = 3

MUTATION_SUCCESS_MARKERS = [
    "생성되었습니다",
    "수정되었습니다",
    "삭제되었습니다",
    '"success": true',
    "'success': True",
]


def is_subquery(query: str) -> bool:
    """Replanning에서 생성된 서브-쿼리인지 확인."""
    subquery_keywords = [
        "이전에 찾은",
        "그 담당자",
        "그 사람",
        "그 액션",
        "그 팀원",
        "그 팀",
        "그 결정",
        "찾은",
    ]
    return any(kw in query for kw in subquery_keywords)


def detect_composite_query(query: str) -> bool:
    """복합 쿼리(여러 단계의 검색이 필요한 쿼리) 감지."""
    assignment_keywords = ["맡고 있는", "담당", "책임자", "담당자", "맡은"]
    team_keywords = ["팀원", "같은 팀", "팀에서", "팀의"]
    has_assignment = any(kw in query for kw in assignment_keywords)
    has_team = any(kw in query for kw in team_keywords)
    return has_assignment and has_team


def extract_next_step_query(query: str) -> str:
    """Turn 1 결과를 바탕으로 Turn 2 서브-쿼리 생성."""
    if "팀원" in query:
        return "이전에 찾은 담당자와 같은 팀의 팀원은 누구인가?"
    if "같은 팀" in query or "팀에서" in query or "팀의" in query:
        return "이전에 찾은 담당자와 같은 팀의 팀원들은 누구인가?"
    return "이전에 찾은 담당자의 팀 정보는?"
