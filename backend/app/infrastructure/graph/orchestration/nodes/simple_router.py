import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import get_fast_llm
from app.infrastructure.graph.orchestration.state import OrchestrationState
from app.prompts.v1.orchestration.simple_router import SIMPLE_QUERY_ROUTER_PROMPT

logger = logging.getLogger(__name__)


class SimpleRouterOutput(BaseModel):
    """간단한 쿼리 라우터의 판정 결과"""
    is_simple_query: bool = Field(description="간단한 쿼리 여부 (True면 planning 스킵)")
    category: str = Field(
        description="쿼리 카테고리 (greeting, sentiment, acknowledgment, nonsense, general_knowledge, unavailable, other)"
    )
    simple_response: str | None = Field(
        default=None,
        description="간단한 쿼리일 경우 제안 응답 (응답 생성기에서 참고용)"
    )
    confidence: float = Field(description="판정 신뢰도 (0.0-1.0)")
    reasoning: str = Field(description="판정 근거")


async def route_simple_query(state: OrchestrationState) -> OrchestrationState:
    """간단한 쿼리 사전 필터링 노드 (Planning 이전)

    Contract:
        reads: messages
        writes: is_simple_query, simple_router_output, response (간단한 쿼리면 직접 설정)
        side-effects: LLM API 호출 (DASH-002, 경량 처리)

    Returns:
        OrchestrationState: 간단한 쿼리 판정 결과 포함
    """
    logger.info("간단한 쿼리 라우팅 단계 진입")

    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""

    if not query:
        logger.warning("쿼리가 비어있습니다")
        return {
            "is_simple_query": False,
            "simple_router_output": {
                "is_simple_query": False,
                "category": "other",
                "simple_response": None,
                "confidence": 0.0,
                "reasoning": "쿼리가 비어있음"
            }
        }

    try:
        # DASH-002 모델 사용 (빠른 응답, 경량 처리)
        parser = PydanticOutputParser(pydantic_object=SimpleRouterOutput)
        prompt = ChatPromptTemplate.from_template(SIMPLE_QUERY_ROUTER_PROMPT)
        chain = prompt | get_fast_llm() | parser

        result = await chain.ainvoke({
            "query": query,
            "format_instructions": parser.get_format_instructions()
        })

        logger.info(f"Simple Router 판정: is_simple={result.is_simple_query}, category={result.category}")

        # 간단한 쿼리인 경우 - 응답 생성기로 라우팅
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
                "need_tools": False,  # 도구 불필요
                "plan": f"간단한 쿼리: {result.category}",
            }
        else:
            # 복잡한 쿼리 - planning으로 보냄
            return {
                "is_simple_query": False,
                "simple_router_output": {
                    "is_simple_query": result.is_simple_query,
                    "category": result.category,
                    "simple_response": None,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                }
            }

    except Exception as e:
        logger.error(f"Simple Router 오류: {e}")
        # 오류 발생 시 planning으로 보냄
        return {
            "is_simple_query": False,
            "simple_router_output": {
                "is_simple_query": False,
                "category": "error",
                "simple_response": None,
                "confidence": 0.0,
                "reasoning": f"라우터 오류: {str(e)}"
            }
        }
