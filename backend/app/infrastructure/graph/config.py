"""LangGraph 오케스트레이션 설정.

구조:
- 환경 변수: API 키, DB 연결 정보 (단일 진실 공급원)
- GraphSettings: 재시도, 타임아웃, 리소스 제약 등 전역 설정

사용 예시:
    from app.infrastructure.graph.config import get_graph_settings
    
    settings = get_graph_settings()
    print(settings.max_retry_count)
"""

from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

_settings = get_settings()

# ============================================================================
# 환경 변수 (단일 진실 공급원)
# ============================================================================

# LLM API 키
NCP_CLOVASTUDIO_API_KEY = _settings.ncp_clovastudio_api_key

# Neo4j 연결
NEO4J_URI = _settings.neo4j_uri
NEO4J_USER = _settings.neo4j_user
NEO4J_PASSWORD = _settings.neo4j_password

# ============================================================================
# 전역 설정 (모든 워크플로우)
# ============================================================================

# Orchestration 설정
MAX_RETRY = 3  # 최대 재시도 횟수
REQUEST_TIMEOUT = 30  # 요청 타임아웃 (초)
MAX_TOKENS = 2048  # LLM 최대 토큰

# MIT Search Selection 설정
MIT_SEARCH_TOP_K = 5  # 선택할 최대 결과 수
MIT_SEARCH_MIN_SCORE = 0.3  # 최소 점수 임계값


class GraphSettings(BaseModel):
    """LangGraph 전역 설정.

    모든 워크플로우(mit_action, mit_search 등)에 적용되는 설정.

    Attributes:
        max_retry_count: 워크플로우 재시도 최대 횟수 (default: 3)
        request_timeout: 외부 API 호출 타임아웃 (초) (default: 30)
        max_tokens: LLM 생성 최대 토큰 수 (default: 2048)
        mit_search_top_k: MIT Search 선택 결과 수 (default: 5)
        mit_search_min_score: MIT Search 최소 점수 임계값 (default: 0.3)
    """

    model_config = ConfigDict(frozen=True)

    max_retry_count: int = MAX_RETRY
    request_timeout: int = REQUEST_TIMEOUT
    max_tokens: int = MAX_TOKENS
    mit_search_top_k: int = MIT_SEARCH_TOP_K
    mit_search_min_score: float = MIT_SEARCH_MIN_SCORE


# ============================================================================
# 싱글톤 팩토리 함수
# ============================================================================

@lru_cache
def get_graph_settings() -> GraphSettings:
    """Graph 전역 설정 싱글톤 반환.

    LangGraph 오케스트레이션 및 모든 서브그래프에서 공용으로 사용하는 설정.
    @lru_cache로 캐싱되므로 여러 번 호출해도 동일한 인스턴스 반환.

    Returns:
        GraphSettings: 캐싱된 전역 설정 인스턴스

    Example:
        >>> settings = get_graph_settings()
        >>> max_retries = settings.max_retry_count
        >>> timeout = settings.request_timeout
    """
    return GraphSettings(
        max_retry_count=MAX_RETRY,
        request_timeout=REQUEST_TIMEOUT,
        max_tokens=MAX_TOKENS,
        mit_search_top_k=MIT_SEARCH_TOP_K,
        mit_search_min_score=MIT_SEARCH_MIN_SCORE
    )
