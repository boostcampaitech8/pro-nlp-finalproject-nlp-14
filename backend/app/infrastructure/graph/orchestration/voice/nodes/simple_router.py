import logging

from app.core.config import get_settings
from app.infrastructure.graph.orchestration.shared.simple_router import SimpleRouterOutput
from ..state import VoiceOrchestrationState

logger = logging.getLogger(__name__)


async def route_simple_query(state: VoiceOrchestrationState) -> VoiceOrchestrationState:
    """간단한 쿼리 사전 필터링 노드 (Planning 이전)

    Clova Router API를 사용하여 쿼리를 분류합니다.

    Contract:
        reads: messages
        writes: is_simple_query, simple_router_output, need_tools, plan
        side-effects: Clova Router API 호출

    Returns:
        VoiceOrchestrationState: 간단한 쿼리 판정 결과 포함
    """
    logger.info("간단한 쿼리 라우팅 단계 진입")

    settings = get_settings()
    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""

    if not query:
        logger.warning("쿼리가 비어있습니다")
        return _create_empty_router_output()

    # Clova Router 필수 설정 확인
    if not settings.clova_router_id:
        error_msg = "CLOVA_ROUTER_ID가 설정되지 않았습니다"
        logger.error(error_msg)
        return _create_error_router_output(error_msg)

    if not settings.ncp_clovastudio_api_key:
        error_msg = "NCP_CLOVASTUDIO_API_KEY가 설정되지 않았습니다"
        logger.error(error_msg)
        return _create_error_router_output(error_msg)

    # Clova Router 호출
    try:
        result = await _route_with_clova(query)
        logger.info(
            f"Clova Router 성공: is_simple={result.is_simple_query}, "
            f"category={result.category}, confidence={result.confidence:.2f}"
        )
        return _create_router_state(result)
    except Exception as e:
        logger.error(f"Clova Router 실패: {e}")
        return _create_error_router_output(str(e))


async def _route_with_clova(query: str) -> SimpleRouterOutput:
    """Clova Router API 호출

    Args:
        query: 사용자 쿼리

    Returns:
        SimpleRouterOutput: 라우팅 결과

    Raises:
        Exception: Clova Router API 호출 실패
    """
    from app.infrastructure.graph.integration.clova_router import ClovaRouterClient
    from app.infrastructure.graph.integration.router_mapper import RouterResponseMapper

    settings = get_settings()

    async with ClovaRouterClient(
        router_id=settings.clova_router_id,
        version=settings.clova_router_version,
        api_key=settings.ncp_clovastudio_api_key,
    ) as client:
        clova_response = await client.route(query)

    # 응답 매핑
    return RouterResponseMapper.map_response(clova_response, query)




def _create_router_state(result: SimpleRouterOutput) -> dict:
    """라우터 결과를 VoiceOrchestrationState로 변환

    Args:
        result: SimpleRouterOutput 인스턴스

    Returns:
        VoiceOrchestrationState 업데이트 딕셔너리
    """
    if result.is_simple_query:
        return {
            "is_simple_query": True,
            "simple_router_output": {
                "is_simple_query": result.is_simple_query,
                "category": result.category,
                "simple_response": result.simple_response,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
            },
            "need_tools": False,
            "plan": f"간단한 쿼리: {result.category}",
        }
    else:
        return {
            "is_simple_query": False,
            "simple_router_output": {
                "is_simple_query": result.is_simple_query,
                "category": result.category,
                "simple_response": None,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
            },
        }


def _create_empty_router_output() -> dict:
    """빈 쿼리 처리

    Returns:
        VoiceOrchestrationState 업데이트 딕셔너리
    """
    return {
        "is_simple_query": False,
        "simple_router_output": {
            "is_simple_query": False,
            "category": "other",
            "simple_response": None,
            "confidence": 0.0,
            "reasoning": "쿼리가 비어있음",
        },
    }


def _create_error_router_output(error_msg: str) -> dict:
    """에러 상황 처리

    Args:
        error_msg: 에러 메시지

    Returns:
        VoiceOrchestrationState 업데이트 딕셔너리
    """
    return {
        "is_simple_query": False,
        "simple_router_output": {
            "is_simple_query": False,
            "category": "error",
            "simple_response": None,
            "confidence": 0.0,
            "reasoning": f"라우터 오류: {error_msg}",
        },
    }
