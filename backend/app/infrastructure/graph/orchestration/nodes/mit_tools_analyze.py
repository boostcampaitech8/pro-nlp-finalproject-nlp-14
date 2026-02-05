import logging

from app.infrastructure.graph.orchestration.state import OrchestrationState
from app.infrastructure.graph.workflows.mit_search.nodes.query_intent_analyzer import (
    query_intent_analyzer_async,
)

logger = logging.getLogger(__name__)


async def execute_mit_tools_analyze(state: OrchestrationState) -> OrchestrationState:
    """MIT-Tools 의도 분석 노드

    Contract:
        reads: messages, user_id, next_subquery
        writes: mit_search_primary_entity, mit_search_query_intent
        side-effects: LLM API 호출 (query_intent_analyzer)
        failures: LLM 오류 → primary_entity=None, 기본 intent 반환

    MIT Search의 query_intent_analyzer만 실행하여 검색 의도를 분석합니다.
    분석된 primary_entity는 event streaming에 사용됩니다.
    """
    logger.info("MIT-Tools 의도 분석 단계 진입")

    messages = state.get('messages', [])
    user_id = state.get('user_id', 'unknown')
    next_subquery = state.get('next_subquery')  # Replanning에서 지정한 서브-쿼리
    
    # next_subquery가 있으면 (replanning 후) 그것을 사용, 아니면 원래 쿼리 사용
    if next_subquery:
        query = next_subquery
        logger.info(f"[Replanning] 서브-쿼리 사용: {query}")
    else:
        query = messages[-1].content if messages else ""

    logger.info(f"의도 분석 쿼리: {query[:50]}..., 사용자: {user_id}")

    try:
        # query_intent_analyzer만 실행
        intent_result = await query_intent_analyzer_async({
            "mit_search_query": query,
            "messages": messages,
            "user_id": user_id,
        })

        # 의도 분석 결과 추출
        query_intent = intent_result.get("mit_search_query_intent", {})
        primary_entity = query_intent.get("primary_entity")
        intent_type = query_intent.get("intent_type", "general_search")
        confidence = query_intent.get("confidence", 0.0)

        logger.info(
            f"✓ 의도 분석 완료: type={intent_type}, "
            f"entity={primary_entity}, confidence={confidence:.2f}"
        )

        return OrchestrationState(
            mit_search_primary_entity=primary_entity,
            mit_search_query_intent=query_intent,
        )

    except Exception as e:
        logger.error(f"MIT-Tools 의도 분석 중 오류: {e}", exc_info=True)
        # 오류 발생 시 기본값 반환
        return OrchestrationState(
            mit_search_primary_entity=None,
            mit_search_query_intent={
                "intent_type": "general_search",
                "primary_entity": None,
                "search_focus": None,
                "confidence": 0.1,
                "reasoning": f"Intent analysis failed: {str(e)}",
            }
        )
