from functools import lru_cache

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
    debug: bool = False

    # 데이터베이스
    database_url: str = "postgresql+asyncpg://mit:mitpassword@localhost:5432/mit"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT 설정
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()
