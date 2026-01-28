"""Realtime Worker 설정"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class RealtimeWorkerConfig(BaseSettings):
    """Realtime Worker 설정"""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent.parent / ".env",  # 프로젝트 루트/.env
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LiveKit 설정
    livekit_ws_url: str = ""
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret_devsecret_devsecret_1234"

    # Clova Speech STT 설정
    clova_stt_endpoint: str = "clovaspeech-gw.ncloud.com:50051"
    clova_stt_secret: str = ""

    # Backend API 설정
    backend_api_url: str = ""
    backend_api_key: str = ""  # 내부 서비스 인증용

    # Agent (LLM) 설정
    agent_enabled: bool = True
    agent_stream_path: str = "/api/v1/agent/meeting"

    # TTS 설정
    tts_server_url: str = ""
    tts_timeout: float = 60.0
    tts_synthesize_path: str = "/tts/synthesize"
    tts_voice: str = "F1"

    # Worker 설정
    log_level: str = "INFO"
    audio_sample_rate: int = 16000  # 16kHz
    audio_channels: int = 1  # mono
    audio_bits_per_sample: int = 16  # 16-bit
    chunk_duration_ms: int = 100  # 100ms 청크 단위

    # 무음 필터링 설정
    silence_threshold: float = 300.0  # RMS 임계값 (0~32768, 낮을수록 민감)


@lru_cache
def get_config() -> RealtimeWorkerConfig:
    """설정 싱글톤 반환"""
    return RealtimeWorkerConfig()
