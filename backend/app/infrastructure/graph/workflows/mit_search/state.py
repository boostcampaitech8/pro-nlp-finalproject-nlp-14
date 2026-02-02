"""MIT Search 서브그래프 State 정의."""

from typing import Annotated, List, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class MitSearchState(TypedDict, total=False):
    """MIT Search 서브그래프 실행을 위한 독립 State.

    메인 그래프와는 필요한 필드만 공유하며, 서브그래프 전용 필드에는
    'mit_search_' 접두사를 사용합니다.
    """

    # 입력/공유 필드 (메인 그래프와 매핑)
    messages: Annotated[List[BaseMessage], add_messages]
    message: NotRequired[str]
    user_id: Annotated[str, "user_id"]

    # 쿼리 처리
    mit_search_query: Annotated[str, "LLM 정규화 후 재작성된 쿼리"]
    mit_search_query_intent: Annotated[
        dict,
        "LLM 분석된 쿼리 의도 + 필터 (intent_type, primary_entity, date_range, entity_types, keywords, ...)",
    ]

    # 검색 전략
    mit_search_strategy: Annotated[dict, "결정된 검색 전략 (strategy, search_term, reasoning)"]

    # Cypher 생성
    mit_search_cypher: Annotated[str, "Neo4j FULLTEXT용 생성된 Cypher 쿼리"]

    # 결과
    mit_search_raw_results: Annotated[list[dict], "Neo4j 원본 결과"]
    mit_search_fallback_used: Annotated[bool, "Fallback 전략 사용 여부"]