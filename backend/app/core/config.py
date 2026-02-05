from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        # backend/app/core/config.py -> project root/.env
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 앱 설정
    app_name: str = "Mit API"
    app_env: str = "production"  # development, production
    debug: bool = False

    # 서버 설정
    host: str = "0.0.0.0"
    port: int = 8000

    # 데이터베이스
    database_url: str = "postgresql+asyncpg://mit:mitpassword@localhost:5432/mit"

    # Neo4j 데이터베이스
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    use_mock_graph: bool = False  # 테스트 시 Mock KG Repository 사용

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT 설정
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS - JSON 배열 형식
    cors_origins: list[str] = ["http://localhost:3000"]

    # OpenAI API (Realtime STT 등)
    openai_api_key: str = ""

    # LLM (Clova Studio) 설정
    ncp_clovastudio_api_key: str = ""

    # ARQ Worker 설정
    arq_redis_url: str = "redis://localhost:6379/1"

    # LiveKit (SFU) 설정
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_ws_url: str = "ws://localhost:7880"  # 내부 통신용
    livekit_external_url: str = "ws://localhost:7880"  # 클라이언트용

    # 네이버 OAuth 설정
    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_redirect_uri: str = "http://localhost:3000/auth/naver/callback"

    # Google OAuth 설정
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/auth/google/callback"

    # Agent 설정
    agent_wake_word: str = "부덕"
    enable_agent_streaming: bool = True  # astream_events() 활성화 (프로토타입)

    # Clova STT 키 관리 설정
    clova_stt_key_count: int = 5  # 사용 가능한 API 키 총 개수

    # Clova Studio Router 설정
    clova_router_id: str = ""  # Clova Studio Router ID
    clova_router_version: int = 1  # Router 버전 (1 이상)

    # Langfuse (LLM Observability)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_tracing_enabled: bool = True

    # 팀 제한 설정
    max_team_members: int = 7  # AI Agent 미포함

    # 초대 링크 설정
    frontend_base_url: str = "http://localhost:3000"  # 초대 링크 URL 생성용

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """쉼표로 구분된 문자열을 리스트로 변환"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def checkpointer_database_url(self) -> str:
        """AsyncPostgresSaver용 psycopg URL

        SQLAlchemy의 asyncpg 드라이버 URL을 psycopg 형식으로 변환.
        postgresql+asyncpg:// -> postgresql://
        """
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()
