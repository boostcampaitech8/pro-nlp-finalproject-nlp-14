"""MIT Search 서브그래프 State 정의."""

from typing import Annotated
from app.infrastructure.graph.orchestration.state import OrchestrationState


class MitSearchState(OrchestrationState, total=False):
    """
    MIT Search 서브그래프 실행을 위한 State.

    OrchestrationState로부터 상속:
    - messages, user_id, plan, need_tools, tool_results, retry_count
    - evaluation, evaluation_status, evaluation_reason, response

    파이프라인 전용 필드 (모두 'mit_search_' 접두사 사용):
        mit_search_query: LLM으로 정규화/재작성된 검색 쿼리
        mit_search_filters: 추출된 시간 및 엔티티 타입 필터
        mit_search_cypher: FULLTEXT 검색용 Neo4j Cypher 쿼리
        mit_search_raw_results: Neo4j에서 가져온 원본 검색 결과 (재랭킹 전)
        mit_search_ranked_results: BGE 점수로 재랭킹된 결과
        mit_search_results: 오케스트레이션 레이어용 최종 포맷 결과
    """

    # 쿼리 처리
    mit_search_query: Annotated[str, "LLM 정규화 후 재작성된 쿼리"]
    mit_search_filters: Annotated[dict, "추출된 date_range와 entity_types"]
    mit_search_query_intent: Annotated[dict, "LLM 분석된 쿼리 의도 (intent_type, primary_entity, ...)"]

    # 검색 전략
    mit_search_strategy: Annotated[dict, "결정된 검색 전략 (strategy, search_term, reasoning)"]

    # Cypher 생성
    mit_search_cypher: Annotated[str, "Neo4j FULLTEXT용 생성된 Cypher 쿼리"]

    # 결과 파이프라인
    mit_search_raw_results: Annotated[list[dict], "Neo4j FULLTEXT 원본 결과"]
    mit_search_ranked_results: Annotated[list[dict], "BGE v2-m3로 재랭킹된 결과"]
    mit_search_results: Annotated[list[dict], "오케스트레이션용 최종 포맷 결과"]
    mit_search_fallback_used: Annotated[bool, "Fallback 전략 사용 여부 (P1)"]

    # 결과 품질 평가
    mit_search_result_quality: Annotated[dict, "결과 관련성 점수 (quality_score, assessment)"]