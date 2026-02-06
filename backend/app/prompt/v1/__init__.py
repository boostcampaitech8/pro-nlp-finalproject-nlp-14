"""Prompt v1 패키지

Version 1.0 프롬프트 모음.
워크플로우별로 구조화되어 있습니다.

패키지 구조:
    - orchestration/: 오케스트레이션 레이어 프롬프트
        - planning: 계획 수립/재계획
        - answering: 최종 응답 생성
    - mit_search/: MIT Search 워크플로우 프롬프트
        - query_intent: 쿼리 의도 분석
        - cypher: Cypher 쿼리 생성
    - workflows/: 데이터 처리 워크플로우 프롬프트
        - mit_suggestion/: Decision 수정 제안 처리
        - mit_action/: Action Item 추출
        - generate_pr/: Agenda/Decision 추출

사용 예시:
    from app.prompt.v1.orchestration.planning import INITIAL_PLANNING_PROMPT
    from app.prompt.v1.mit_search.cypher import CYPHER_GENERATION_SYSTEM_PROMPT
    from app.prompt.v1.workflows.generate_pr import AGENDA_EXTRACTION_PROMPT
"""

from . import orchestration
from . import mit_search
from . import workflows
from . import context

__all__ = [
    "orchestration",
    "mit_search",
    "workflows",
    "context",
]
