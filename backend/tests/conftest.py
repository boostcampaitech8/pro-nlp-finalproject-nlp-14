"""pytest 설정 및 공유 fixture

테스트 인프라:
- 테스트 DB 세션
- FastAPI TestClient
- Mock 서비스 (MinIO, Redis)
- 테스트 데이터 fixture
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.core.database import Base, get_db
from app.main import app
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, ParticipantRole
from app.models.team import Team, TeamMember, TeamRole
from app.models.user import AuthProvider, User


# ===== 테스트 설정 =====


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """테스트용 설정

    환경변수 TEST_DATABASE_URL이 있으면 사용, 없으면 기본값 사용
    """
    test_db_url = os.getenv(
        "TEST_DATABASE_URL", "postgresql+asyncpg://mit:mitpassword@localhost:5432/mit_test"
    )

    return Settings(
        app_env="test",
        debug=True,
        database_url=test_db_url,
        redis_url="redis://localhost:6379/1",  # 테스트용 DB 1 사용
        jwt_secret_key="test-secret-key",
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin",
        minio_secure=False,
    )


# ===== 데이터베이스 Fixture =====


@pytest.fixture
async def test_engine(test_settings: Settings):
    """테스트용 비동기 엔진

    각 테스트마다 새 엔진 생성 (더 나은 테스트 격리)
    """
    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
        poolclass=NullPool,  # 테스트에서는 pool 사용 안 함
    )

    # 테이블 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 테이블 삭제
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """테스트용 DB 세션 (function scope)

    각 테스트마다 새 세션 생성 및 자동 롤백
    """
    # 트랜잭션 시작
    connection = await test_engine.connect()
    transaction = await connection.begin()

    # 세션 생성
    session_maker = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    session = session_maker()

    # Nested transaction을 위한 savepoint 활성화
    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    # 테스트 후 롤백 (테스트 격리 보장)
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
def override_get_db(db_session: AsyncSession):
    """FastAPI 의존성 오버라이드용 DB fixture"""

    async def _override_get_db():
        yield db_session

    return _override_get_db


# ===== FastAPI Client Fixture =====


@pytest.fixture
def client(override_get_db) -> Generator[TestClient, None, None]:
    """동기 FastAPI TestClient

    간단한 API 테스트에 사용
    """
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """비동기 FastAPI TestClient

    비동기 엔드포인트 테스트에 사용
    """
    from httpx import ASGITransport

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ===== Mock Services =====


@pytest.fixture
def mock_storage_service():
    """MinIO 스토리지 서비스 Mock"""
    with patch("app.core.storage.storage_service") as mock:
        # upload 메서드
        mock.upload_file.return_value = "recordings/test-meeting/test-file.webm"
        mock.upload_recording.return_value = "recordings/test-meeting/test-file.webm"
        mock.upload_recording_file.return_value = "recordings/test-meeting/test-file.webm"

        # presigned URL 메서드
        mock.get_presigned_url.return_value = "https://minio.test/presigned-download-url"
        mock.get_presigned_upload_url.return_value = (
            "https://minio.test/presigned-upload-url",
            "recordings/test-meeting/test-file.webm",
        )
        mock.get_recording_url.return_value = "https://minio.test/presigned-download-url"
        mock.get_recording_upload_url.return_value = (
            "https://minio.test/presigned-upload-url",
            "recordings/test-meeting/test-file.webm",
        )

        # 파일 정보 메서드
        mock.get_file_info.return_value = {
            "size": 1024 * 1024,  # 1MB
            "etag": "test-etag",
            "last_modified": "2026-01-08T12:00:00Z",
        }

        # 파일 다운로드
        mock.get_file.return_value = b"test file content"
        mock.get_recording_file.return_value = b"test recording content"

        # 삭제
        mock.delete_file.return_value = None
        mock.delete_recording.return_value = None

        yield mock


@pytest.fixture
def mock_redis():
    """Redis Mock (fakeredis 사용 권장, 여기서는 간단한 Mock)"""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=0)

    return mock


# ===== 테스트 데이터 Fixture =====


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """테스트용 사용자"""
    user = User(
        id=uuid4(),
        email="test@example.com",
        name="테스트 사용자",
        auth_provider=AuthProvider.LOCAL.value,
        provider_id="test-provider-id",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user2(db_session: AsyncSession) -> User:
    """두 번째 테스트용 사용자"""
    user = User(
        id=uuid4(),
        email="test2@example.com",
        name="테스트 사용자2",
        auth_provider=AuthProvider.LOCAL.value,
        provider_id="test-provider-id-2",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_team(db_session: AsyncSession, test_user: User) -> Team:
    """테스트용 팀 (소유자: test_user)"""
    team = Team(
        id=uuid4(),
        name="테스트 팀",
        description="테스트용 팀입니다",
        created_by=test_user.id,
    )
    db_session.add(team)
    await db_session.flush()

    # 팀 멤버 추가 (소유자)
    team_member = TeamMember(
        team_id=team.id,
        user_id=test_user.id,
        role=TeamRole.OWNER.value,
    )
    db_session.add(team_member)

    await db_session.commit()
    await db_session.refresh(team)
    return team


@pytest.fixture
async def test_meeting(db_session: AsyncSession, test_team: Team, test_user: User) -> Meeting:
    """테스트용 회의 (호스트: test_user)"""
    meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="테스트 회의",
        description="테스트용 회의입니다",
        created_by=test_user.id,
        status=MeetingStatus.SCHEDULED.value,
    )
    db_session.add(meeting)
    await db_session.flush()

    # 회의 참여자 추가 (호스트)
    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=test_user.id,
        role=ParticipantRole.HOST.value,
    )
    db_session.add(participant)

    await db_session.commit()
    await db_session.refresh(meeting)
    return meeting


@pytest.fixture
def test_auth_token(test_user: User) -> str:
    """테스트용 JWT 토큰

    실제 토큰 생성 로직을 사용하려면 auth_service를 import해서 사용
    여기서는 간단한 mock 토큰 반환
    """
    # 실제로는 app.core.security.create_access_token() 사용
    # 지금은 간단히 "test-token" 반환
    return "test-token-" + str(test_user.id)


@pytest.fixture
def auth_headers(test_auth_token: str) -> dict[str, str]:
    """테스트용 인증 헤더"""
    return {"Authorization": f"Bearer {test_auth_token}"}


# ===== 유틸리티 함수 =====


def assert_uuid(value: Any) -> UUID:
    """UUID 검증 및 변환"""
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise ValueError(f"Invalid UUID: {value}")
