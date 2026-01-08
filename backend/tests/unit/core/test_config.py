"""설정 관련 단위 테스트"""

import pytest

from app.core.config import Settings


def test_settings_creation():
    """설정 객체 생성 테스트"""
    settings = Settings(
        app_env="test",
        debug=True,
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_db",
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret",
    )

    assert settings.app_env == "test"
    assert settings.debug is True
    assert "postgresql+asyncpg" in settings.database_url
    assert settings.jwt_algorithm == "HS256"  # 기본값


def test_settings_from_fixture(test_settings: Settings):
    """Fixture로부터 설정 로드 테스트"""
    assert test_settings.app_env == "test"
    assert test_settings.debug is True
    assert "mit_test" in test_settings.database_url
    assert test_settings.redis_url == "redis://localhost:6379/1"
    assert test_settings.jwt_secret_key == "test-secret-key"
