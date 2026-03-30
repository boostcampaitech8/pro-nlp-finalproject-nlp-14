"""초대 링크 API 엔드포인트 단위 테스트

총 10개 테스트:
- POST /teams/{team_id}/invite-link: 2개 (성공, 권한 없음)
- GET /teams/{team_id}/invite-link: 2개 (성공, 링크 없음)
- DELETE /teams/{team_id}/invite-link: 2개 (성공, 링크 없음)
- GET /invite/{code}: 2개 (성공-비인증, 만료)
- POST /invite/{code}/accept: 2개 (성공, 이미 멤버)

DB 의존 없이 서비스 레이어를 mock하여 API 동작만 검증합니다.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.invite_link import (
    AcceptInviteResponse,
    InviteLinkResponse,
    InvitePreviewResponse,
)


# ===== 자체 Fixture (DB 불필요) =====


@pytest.fixture
def mock_user():
    """DB 없는 mock User 객체"""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.name = "테스트 사용자"
    return user


@pytest.fixture
def mock_team_id():
    """mock 팀 ID"""
    return uuid4()


@pytest.fixture
def mock_invite_service():
    """InviteLinkService mock"""
    return AsyncMock()


@pytest.fixture
async def api_client():
    """DB 독립적인 async client"""
    from app.core.database import get_db
    from app.main import app

    # get_db를 mock으로 오버라이드하여 DB 연결 방지
    async def mock_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = mock_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)


# ===== POST /teams/{team_id}/invite-link =====


@pytest.mark.asyncio
async def test_generate_invite_link_api_success(
    api_client: AsyncClient,
    mock_team_id,
    mock_user,
    mock_invite_service,
):
    """초대 링크 생성 API 성공"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    now = datetime.now(timezone.utc)
    mock_invite_service.generate_invite_link = AsyncMock(
        return_value=InviteLinkResponse(
            code="test1234",
            invite_url="http://localhost:3000/invite/test1234",
            team_id=mock_team_id,
            created_by=mock_user.id,
            created_at=now,
            expires_at=now,
        )
    )

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.post(f"/api/v1/teams/{mock_team_id}/invite-link")

        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "test1234"
        assert "inviteUrl" in data
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)


@pytest.mark.asyncio
async def test_generate_invite_link_api_permission_denied(
    api_client: AsyncClient,
    mock_team_id,
    mock_user,
    mock_invite_service,
):
    """권한 없는 사용자의 초대 링크 생성 요청"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.generate_invite_link = AsyncMock(
        side_effect=ValueError("PERMISSION_DENIED")
    )

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.post(f"/api/v1/teams/{mock_team_id}/invite-link")

        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "FORBIDDEN"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)


# ===== GET /teams/{team_id}/invite-link =====


@pytest.mark.asyncio
async def test_get_invite_link_api_success(
    api_client: AsyncClient,
    mock_team_id,
    mock_user,
    mock_invite_service,
):
    """활성 초대 링크 조회 성공"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    now = datetime.now(timezone.utc)
    mock_invite_service.get_active_invite_link = AsyncMock(
        return_value=InviteLinkResponse(
            code="abc12345",
            invite_url="http://localhost:3000/invite/abc12345",
            team_id=mock_team_id,
            created_by=mock_user.id,
            created_at=now,
            expires_at=now,
        )
    )

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.get(f"/api/v1/teams/{mock_team_id}/invite-link")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "abc12345"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)


@pytest.mark.asyncio
async def test_get_invite_link_api_not_found(
    api_client: AsyncClient,
    mock_team_id,
    mock_user,
    mock_invite_service,
):
    """활성 초대 링크가 없는 경우 404"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.get_active_invite_link = AsyncMock(return_value=None)

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.get(f"/api/v1/teams/{mock_team_id}/invite-link")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)


# ===== DELETE /teams/{team_id}/invite-link =====


@pytest.mark.asyncio
async def test_deactivate_invite_link_api_success(
    api_client: AsyncClient,
    mock_team_id,
    mock_user,
    mock_invite_service,
):
    """초대 링크 비활성화 성공"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.deactivate_invite_link = AsyncMock(return_value=None)

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.delete(f"/api/v1/teams/{mock_team_id}/invite-link")

        assert response.status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)


@pytest.mark.asyncio
async def test_deactivate_invite_link_api_not_found(
    api_client: AsyncClient,
    mock_team_id,
    mock_user,
    mock_invite_service,
):
    """비활성화할 초대 링크가 없는 경우 404"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.deactivate_invite_link = AsyncMock(
        side_effect=ValueError("INVITE_NOT_FOUND")
    )

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.delete(f"/api/v1/teams/{mock_team_id}/invite-link")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)


# ===== GET /invite/{code} (공개 엔드포인트) =====


@pytest.mark.asyncio
async def test_preview_invite_api_success(
    api_client: AsyncClient,
    mock_invite_service,
):
    """초대 링크 미리보기 (인증 불필요)"""
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.preview_invite = AsyncMock(
        return_value=InvitePreviewResponse(
            team_name="테스트 팀",
            team_description="설명",
            member_count=3,
            max_members=7,
        )
    )

    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.get("/api/v1/invite/test_code")

        assert response.status_code == 200
        data = response.json()
        assert data["teamName"] == "테스트 팀"
        assert data["memberCount"] == 3
        assert data["maxMembers"] == 7
    finally:
        app.dependency_overrides.pop(get_invite_link_service, None)


@pytest.mark.asyncio
async def test_preview_invite_api_expired(
    api_client: AsyncClient,
    mock_invite_service,
):
    """만료된 초대 링크 미리보기"""
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.preview_invite = AsyncMock(
        side_effect=ValueError("INVITE_NOT_FOUND")
    )

    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.get("/api/v1/invite/expired_code")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_invite_link_service, None)


# ===== POST /invite/{code}/accept =====


@pytest.mark.asyncio
async def test_accept_invite_api_success(
    api_client: AsyncClient,
    mock_team_id,
    mock_user,
    mock_invite_service,
):
    """초대 수락 성공"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.accept_invite = AsyncMock(
        return_value=AcceptInviteResponse(
            team_id=mock_team_id,
            role="member",
        )
    )

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.post("/api/v1/invite/valid_code/accept")

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "member"
        assert "teamId" in data
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)


@pytest.mark.asyncio
async def test_accept_invite_api_already_member(
    api_client: AsyncClient,
    mock_user,
    mock_invite_service,
):
    """이미 팀 멤버인 경우 409 Conflict"""
    from app.api.dependencies import get_current_user
    from app.api.v1.endpoints.invite_links import get_invite_link_service
    from app.main import app

    mock_invite_service.accept_invite = AsyncMock(
        side_effect=ValueError("ALREADY_MEMBER")
    )

    async def override_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_invite_link_service] = lambda: mock_invite_service

    try:
        response = await api_client.post("/api/v1/invite/valid_code/accept")

        assert response.status_code == 409
        assert response.json()["detail"]["error"] == "CONFLICT"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_invite_link_service, None)
