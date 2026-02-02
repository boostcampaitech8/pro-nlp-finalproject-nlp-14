"""Context Configuration

컨텍스트 엔지니어링 설정 (Topic-Segmented)

주의:
- 토큰 예산은 HCX-003 (8K) 기준으로 산정
- 모든 설정은 환경변수로 오버라이드 가능 (CONTEXT_ prefix)
"""

from pydantic_settings import BaseSettings


class ContextConfig(BaseSettings):
    """컨텍스트 엔지니어링 설정

    환경변수 예시:
    - CONTEXT_L0_MAX_TURNS=25
    - CONTEXT_L1_UPDATE_TURN_THRESHOLD=25
    """

    # === L0 설정 (Raw Window) ===
    l0_max_turns: int = 25  # 최대 턴 수 (HCX-003 8K 기준)
    l0_max_tokens: int = 3000  # 최대 토큰 수 (초과 시 오래된 것부터 제거)
    l0_include_timestamps: bool = True  # 타임스탬프 포함 여부

    # L0 토픽 버퍼 설정 (무한 증식 방지)
    l0_topic_buffer_max_turns: int = 100  # 토픽 내 최대 발화 수
    l0_topic_buffer_max_tokens: int = 10000  # 토픽 내 최대 토큰

    # === L1 설정 (Topic-Segmented) ===
    l1_update_turn_threshold: int = 25  # 턴 기반 업데이트 임계값

    # === 화자 컨텍스트 설정 ===
    speaker_buffer_max_per_speaker: int = 25  # 화자별 최대 발화 버퍼 크기

    # === 토픽 메모리 설정 (L1 + Semantic Search) ===
    max_topics: int = 30  # 최대 토픽 수
    topic_merge_threshold: float = 0.80  # 유사 토픽 병합 임계값
    topic_similarity_threshold: float = 0.85  # 재귀 병합 임계값

    # === 임베딩 설정 (CLOVA Studio API) ===
    embedding_model: str = "bge-m3"  # CLOVA Studio 지원 모델
    embedding_dimension: int = 1024

    # === 시맨틱 서치 설정 ===
    topic_search_top_k: int = 5
    topic_search_threshold: float = 0.30

    class Config:
        env_prefix = "CONTEXT_"
        case_sensitive = False
