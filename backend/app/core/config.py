from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
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
    neo4j_database: str = "neo4j"
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

    # MinIO (Object Storage)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    # 외부에서 접근 가능한 스토리지 URL (nginx 프록시 경로)
    # 예: https://www.mit-hub.com/storage
    storage_external_url: str = "http://localhost:3000/storage"

    # STT (Speech-to-Text) 설정
    openai_api_key: str = ""
    stt_provider: str = "openai"  # openai, local, self_hosted

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

    # Neo4j 설정
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    use_mock_graph: bool = False

    # LangGraph 설정
    ncp_clovastudio_api_key: str = ""

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


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()
