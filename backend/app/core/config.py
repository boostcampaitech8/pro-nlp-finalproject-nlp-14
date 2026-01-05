from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 앱 설정
    app_name: str = "Mit API"
    app_env: str = "development"  # development, production
    debug: bool = False

    # 서버 설정
    host: str = "0.0.0.0"
    port: int = 8000

    # 데이터베이스
    database_url: str = "postgresql+asyncpg://mit:mitpassword@localhost:5432/mit"

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
