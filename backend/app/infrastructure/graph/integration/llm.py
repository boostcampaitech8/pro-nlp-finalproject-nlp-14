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
