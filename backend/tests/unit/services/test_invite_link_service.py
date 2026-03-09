"""초대 링크 서비스 단위 테스트 (Mock 기반, DB 불필요)

총 17개 테스트:
- generate_invite_link: 4개 (성공, 기존 링크 교체, 권한 없음, 멤버 아님)
- get_active_invite_link: 3개 (성공, 링크 없음, 멤버 아님)
- deactivate_invite_link: 3개 (성공, 권한 없음, 링크 없음)
- preview_invite: 2개 (성공, 만료/없음)
- accept_invite: 5개 (성공, 이미 멤버, 정원 초과, 만료, Neo4j 동기화)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.team import Team, TeamMember, TeamRole
from app.models.user import User
from app.services.invite_link_service import InviteLinkService


# ===== Fixtures =====


@pytest.fixture
def mock_redis():
    """Redis mock with async methods"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.ttl = AsyncMock(return_value=3600)
    return redis


@pytest.fixture
def mock_neo4j():
    """Neo4j sync mock"""
    neo4j = AsyncMock()
    neo4j.sync_member_of_create = AsyncMock()
    return neo4j


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def user2_id():
    return uuid4()


@pytest.fixture
def team_id():
    return uuid4()


def make_owner_member(team_id, user_id):
    """owner TeamMember mock 생성"""
    m = MagicMock(spec=TeamMember)
    m.team_id = team_id
    m.user_id = user_id
    m.role = TeamRole.OWNER.value
    return m


def make_member(team_id, user_id):
    """member TeamMember mock 생성"""
    m = MagicMock(spec=TeamMember)
    m.team_id = team_id
    m.user_id = user_id
    m.role = TeamRole.MEMBER.value
    return m


def make_team(team_id, name="테스트 팀", description="테스트 설명"):
    """Team mock 생성"""
    t = MagicMock(spec=Team)
    t.id = team_id
    t.name = name
    t.description = description
    return t


def mock_db_session():
    """DB session mock"""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


def make_scalar_result(value):
    """SQLAlchemy scalar_one_or_none 결과를 반환하는 mock"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar.return_value = value
    return result


# ===== generate_invite_link 테스트 (4개) =====


@pytest.mark.asyncio
async def test_generate_invite_link_success(team_id, user_id, mock_redis, mock_neo4j):
    """owner가 초대 링크를 성공적으로 생성"""
    db = mock_db_session()

    # _get_team_member → owner 반환
    owner = make_owner_member(team_id, user_id)
    team = make_team(team_id)

    call_count = 0

    async def execute_side_effect(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_scalar_result(owner)  # _get_team_member
        if call_count == 2:
            return make_scalar_result(team)  # _get_team
        return make_scalar_result(None)

    db.execute = AsyncMock(side_effect=execute_side_effect)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        result = await service.generate_invite_link(team_id, user_id)

    assert result.code is not None
    assert len(result.code) > 0
    assert result.team_id == team_id
    assert result.created_by == user_id
    assert result.invite_url is not None
    assert result.expires_at is not None

    # Redis에 2개 키 저장 확인
    assert mock_redis.set.call_count == 2


@pytest.mark.asyncio
async def test_generate_invite_link_replaces_existing(team_id, user_id, mock_redis, mock_neo4j):
    """기존 초대 링크가 있으면 삭제 후 새로 생성"""
    db = mock_db_session()
    owner = make_owner_member(team_id, user_id)
    team = make_team(team_id)

    call_count = 0

    async def execute_side_effect(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_scalar_result(owner)
        if call_count == 2:
            return make_scalar_result(team)
        return make_scalar_result(None)

    db.execute = AsyncMock(side_effect=execute_side_effect)

    # 기존 링크가 있는 상태 설정
    mock_redis.get = AsyncMock(
        side_effect=lambda key: "old_code" if "invite:team:" in key else None
    )

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        result = await service.generate_invite_link(team_id, user_id)

    assert result.code is not None
    # 기존 키 삭제 확인 (invite:old_code, invite:team:{team_id})
    assert mock_redis.delete.call_count == 2


@pytest.mark.asyncio
async def test_generate_invite_link_permission_denied(team_id, user2_id, mock_redis, mock_neo4j):
    """member 역할은 초대 링크 생성 불가"""
    db = mock_db_session()
    member = make_member(team_id, user2_id)
    db.execute = AsyncMock(return_value=make_scalar_result(member))

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="PERMISSION_DENIED"):
            await service.generate_invite_link(team_id, user2_id)


@pytest.mark.asyncio
async def test_generate_invite_link_not_team_member(team_id, user2_id, mock_redis, mock_neo4j):
    """팀 멤버가 아닌 사용자는 초대 링크 생성 불가"""
    db = mock_db_session()
    db.execute = AsyncMock(return_value=make_scalar_result(None))

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="NOT_TEAM_MEMBER"):
            await service.generate_invite_link(team_id, user2_id)


# ===== get_active_invite_link 테스트 (3개) =====


@pytest.mark.asyncio
async def test_get_active_invite_link_success(team_id, user_id, mock_redis, mock_neo4j):
    """활성 초대 링크 조회 성공"""
    db = mock_db_session()
    owner = make_owner_member(team_id, user_id)
    db.execute = AsyncMock(return_value=make_scalar_result(owner))

    invite_data = json.dumps({
        "team_id": str(team_id),
        "created_by": str(user_id),
        "created_at": "2026-01-01T00:00:00+00:00",
    })

    def redis_get_side_effect(key):
        if "invite:team:" in key:
            return "test_code"
        if key == "invite:test_code":
            return invite_data
        return None

    mock_redis.get = AsyncMock(side_effect=redis_get_side_effect)
    mock_redis.ttl = AsyncMock(return_value=1800)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        result = await service.get_active_invite_link(team_id, user_id)

    assert result is not None
    assert result.code == "test_code"
    assert result.team_id == team_id


@pytest.mark.asyncio
async def test_get_active_invite_link_none(team_id, user_id, mock_redis, mock_neo4j):
    """활성 초대 링크가 없는 경우 None 반환"""
    db = mock_db_session()
    owner = make_owner_member(team_id, user_id)
    db.execute = AsyncMock(return_value=make_scalar_result(owner))
    mock_redis.get = AsyncMock(return_value=None)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        result = await service.get_active_invite_link(team_id, user_id)

    assert result is None


@pytest.mark.asyncio
async def test_get_active_invite_link_not_member(team_id, user2_id, mock_redis, mock_neo4j):
    """팀 멤버가 아닌 사용자는 초대 링크 조회 불가"""
    db = mock_db_session()
    db.execute = AsyncMock(return_value=make_scalar_result(None))

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="NOT_TEAM_MEMBER"):
            await service.get_active_invite_link(team_id, user2_id)


# ===== deactivate_invite_link 테스트 (3개) =====


@pytest.mark.asyncio
async def test_deactivate_invite_link_success(team_id, user_id, mock_redis, mock_neo4j):
    """owner가 초대 링크를 비활성화"""
    db = mock_db_session()
    owner = make_owner_member(team_id, user_id)
    db.execute = AsyncMock(return_value=make_scalar_result(owner))
    mock_redis.get = AsyncMock(return_value="existing_code")

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        await service.deactivate_invite_link(team_id, user_id)

    assert mock_redis.delete.call_count == 2


@pytest.mark.asyncio
async def test_deactivate_invite_link_permission_denied(team_id, user2_id, mock_redis, mock_neo4j):
    """member 역할은 초대 링크 비활성화 불가"""
    db = mock_db_session()
    member = make_member(team_id, user2_id)
    db.execute = AsyncMock(return_value=make_scalar_result(member))

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="PERMISSION_DENIED"):
            await service.deactivate_invite_link(team_id, user2_id)


@pytest.mark.asyncio
async def test_deactivate_invite_link_not_found(team_id, user_id, mock_redis, mock_neo4j):
    """비활성화할 초대 링크가 없는 경우"""
    db = mock_db_session()
    owner = make_owner_member(team_id, user_id)
    db.execute = AsyncMock(return_value=make_scalar_result(owner))
    mock_redis.get = AsyncMock(return_value=None)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="INVITE_NOT_FOUND"):
            await service.deactivate_invite_link(team_id, user_id)


# ===== preview_invite 테스트 (2개) =====


@pytest.mark.asyncio
async def test_preview_invite_success(team_id, user_id, mock_redis, mock_neo4j):
    """초대 링크 미리보기 성공"""
    db = mock_db_session()
    team = make_team(team_id)

    invite_data = json.dumps({
        "team_id": str(team_id),
        "created_by": str(user_id),
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    mock_redis.get = AsyncMock(return_value=invite_data)

    call_count = 0

    async def execute_side_effect(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_scalar_result(team)  # _get_team
        return make_scalar_result(3)  # _count_members

    db.execute = AsyncMock(side_effect=execute_side_effect)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        result = await service.preview_invite("test_code")

    assert result.team_name == "테스트 팀"
    assert result.team_description == "테스트 설명"
    assert result.member_count == 3
    assert result.max_members == 7


@pytest.mark.asyncio
async def test_preview_invite_expired(mock_redis, mock_neo4j):
    """만료되거나 존재하지 않는 초대 링크 미리보기"""
    db = mock_db_session()
    mock_redis.get = AsyncMock(return_value=None)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="INVITE_NOT_FOUND"):
            await service.preview_invite("expired_code")


# ===== accept_invite 테스트 (5개) =====


@pytest.mark.asyncio
async def test_accept_invite_success(team_id, user2_id, mock_redis, mock_neo4j):
    """초대 수락 성공 (MEMBER 역할로 가입)"""
    db = mock_db_session()

    invite_data = json.dumps({
        "team_id": str(team_id),
        "created_by": str(uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    mock_redis.get = AsyncMock(return_value=invite_data)

    call_count = 0

    async def execute_side_effect(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_scalar_result(None)  # _get_team_member → None (비멤버)
        return make_scalar_result(2)  # _count_members → 2

    db.execute = AsyncMock(side_effect=execute_side_effect)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        result = await service.accept_invite("valid_code", user2_id)

    assert result.team_id == team_id
    assert result.role == TeamRole.MEMBER.value
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_accept_invite_already_member(team_id, user_id, mock_redis, mock_neo4j):
    """이미 팀 멤버인 경우 가입 불가"""
    db = mock_db_session()
    existing = make_owner_member(team_id, user_id)

    invite_data = json.dumps({
        "team_id": str(team_id),
        "created_by": str(uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    mock_redis.get = AsyncMock(return_value=invite_data)
    db.execute = AsyncMock(return_value=make_scalar_result(existing))

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="ALREADY_MEMBER"):
            await service.accept_invite("valid_code", user_id)


@pytest.mark.asyncio
async def test_accept_invite_team_full(team_id, user2_id, mock_redis, mock_neo4j):
    """팀 정원 초과 시 가입 불가"""
    db = mock_db_session()

    invite_data = json.dumps({
        "team_id": str(team_id),
        "created_by": str(uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    mock_redis.get = AsyncMock(return_value=invite_data)

    call_count = 0

    async def execute_side_effect(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_scalar_result(None)  # _get_team_member → None
        return make_scalar_result(7)  # _count_members → 7 (가득 참)

    db.execute = AsyncMock(side_effect=execute_side_effect)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="TEAM_MEMBER_LIMIT_EXCEEDED"):
            await service.accept_invite("valid_code", user2_id)


@pytest.mark.asyncio
async def test_accept_invite_expired(user2_id, mock_redis, mock_neo4j):
    """만료된 초대 링크로 가입 불가"""
    db = mock_db_session()
    mock_redis.get = AsyncMock(return_value=None)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)

        with pytest.raises(ValueError, match="INVITE_NOT_FOUND"):
            await service.accept_invite("expired_code", user2_id)


@pytest.mark.asyncio
async def test_accept_invite_neo4j_sync(team_id, user2_id, mock_redis, mock_neo4j):
    """초대 수락 시 Neo4j에 멤버 동기화"""
    db = mock_db_session()

    invite_data = json.dumps({
        "team_id": str(team_id),
        "created_by": str(uuid4()),
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    mock_redis.get = AsyncMock(return_value=invite_data)

    call_count = 0

    async def execute_side_effect(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_scalar_result(None)
        return make_scalar_result(2)

    db.execute = AsyncMock(side_effect=execute_side_effect)

    with (
        patch("app.services.invite_link_service.get_redis", return_value=mock_redis),
        patch("app.services.invite_link_service.neo4j_sync", mock_neo4j),
    ):
        service = InviteLinkService(db)
        await service.accept_invite("valid_code", user2_id)

    mock_neo4j.sync_member_of_create.assert_called_once_with(
        str(user2_id),
        str(team_id),
        TeamRole.MEMBER.value,
    )
