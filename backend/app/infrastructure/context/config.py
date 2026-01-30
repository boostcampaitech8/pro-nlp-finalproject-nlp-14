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
    - CONTEXT_TOPIC_QUICK_CHECK_ENABLED=true
    """

    # === L0 설정 (Raw Window) ===
    l0_max_turns: int = 25  # 최대 턴 수 (HCX-003 8K 기준)
    l0_max_tokens: int = 3000  # 최대 토큰 수 (초과 시 오래된 것부터 제거)
    l0_include_timestamps: bool = True  # 타임스탬프 포함 여부

    # L0 토픽 버퍼 설정 (무한 증식 방지)
    l0_topic_buffer_max_turns: int = 100  # 토픽 내 최대 발화 수
    l0_topic_buffer_max_tokens: int = 10000  # 토픽 내 최대 토큰

    # === L1 설정 (Topic-Segmented) ===
    l1_topic_check_interval_turns: int = 5  # 토픽 전환 체크 주기 (턴 단위)
    l1_update_interval_minutes: int = 15  # 시간 기반 업데이트 주기 (분)
    l1_update_turn_threshold: int = 25  # 턴 기반 업데이트 임계값
    l1_summary_max_tokens: int = 500  # 요약 최대 토큰 (HCX-003 기준)
    l1_min_new_utterances_for_time_trigger: int = 5  # 시간 트리거를 위한 최소 새 발화 수

    # === 토픽 감지 설정 ===
    topic_quick_check_enabled: bool = True  # 키워드 기반 빠른 감지 활성화

    # === LLM 설정 (HCX-003 기준) ===
    summary_model_name: str = "HCX-003"  # 요약용
    topic_detection_model_name: str = "HCX-003"  # 토픽 감지용

    # === 화자 컨텍스트 설정 ===
    speaker_buffer_max_per_speaker: int = 25  # 화자별 최대 발화 버퍼 크기

    class Config:
        env_prefix = "CONTEXT_"
        case_sensitive = False
