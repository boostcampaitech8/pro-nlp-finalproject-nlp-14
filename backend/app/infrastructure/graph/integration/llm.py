"""LangChain LLM 통합 및 용도별 인스턴스 관리."""

from functools import lru_cache

from langchain_community.chat_models import ChatClovaX

from app.infrastructure.graph.config import NCP_CLOVASTUDIO_API_KEY


@lru_cache
def get_base_llm() -> ChatClovaX:
    """Base LLM 인스턴스 반환 (cached)"""
    if not NCP_CLOVASTUDIO_API_KEY:
        raise ValueError(
            "NCP_CLOVASTUDIO_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 NCP_CLOVASTUDIO_API_KEY를 설정해주세요."
        )
    
    return ChatClovaX(
        temperature=0.5,
        max_tokens=256,
        model="HCX-003",
        ncp_clovastudio_api_key=NCP_CLOVASTUDIO_API_KEY,
    )


def get_planner_llm() -> ChatClovaX:
    """Planning 전용 LLM (낮은 temperature)"""
    return get_base_llm().bind(temperature=0.3)


def get_generator_llm() -> ChatClovaX:
    """Generator 전용 LLM (기본 temperature)"""
    return get_base_llm()


def get_evaluator_llm() -> ChatClovaX:
    """Evaluator 전용 LLM (낮은 temperature)"""
    return get_base_llm().bind(temperature=0.3)


# ============================================================================
# MIT Search용 LLM 인스턴스
# ============================================================================

def get_query_rewriter_llm() -> ChatClovaX:
    """쿼리 정규화 LLM (창의성 높음).

    temperature: 0.7 (창의적인 정규화)
    max_tokens: 256
    """
    return get_base_llm().bind(temperature=0.7, max_tokens=256)


def get_filter_extractor_llm() -> ChatClovaX:
    """필터 추출 LLM (정확도 높음).

    temperature: 0.2 (정확한 추출)
    max_tokens: 512
    """
    return get_base_llm().bind(temperature=0.2, max_tokens=512)


def get_cypher_generator_llm() -> ChatClovaX:
    """Cypher 생성 LLM (정확도 최고).

    temperature: 0.05 (극도로 일관된 쿼리 생성 - 같은 의도는 항상 같은 구조)
    max_tokens: 512
    """
    return get_base_llm().bind(temperature=0.05, max_tokens=512)


def get_answer_generator_llm() -> ChatClovaX:
    """답변 생성 LLM (창의성 중간).

    temperature: 0.5 (자연스러운 답변)
    max_tokens: 1024
    """
    return get_base_llm().bind(temperature=0.5, max_tokens=1024)


def get_llm() -> ChatClovaX:
    """기본 LLM (하위호환성, 새로운 코드는 용도별 함수 사용).

    Returns:
        ChatClovaX: Configured LLM instance
    """
    return get_base_llm()


# 하위 호환성을 위한 변수 export
# 지연 로딩으로 변경: 모듈 import 시점에 평가하지 않음
def _lazy_llm():
    try:
        return get_llm()
    except ValueError:
        # 테스트 환경에서 API 키가 없을 수 있음
        return None

try:
    llm = get_llm()
except ValueError:
    # 테스트 환경에서는 None으로 초기화
    llm = None
