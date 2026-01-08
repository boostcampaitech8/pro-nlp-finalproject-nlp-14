"""인증 서비스 단위 테스트

총 15개 테스트:
- register: 3개 (성공, 이메일 중복, 비밀번호 해싱)
- login: 4개 (성공, 잘못된 이메일, 잘못된 비밀번호, 토큰 생성)
- get_user_by_email: 2개 (성공, 실패)
- get_user_by_id: 2개 (성공, 실패)
- refresh_token: 2개 (성공, 유효하지 않은 토큰)
- get_current_user: 2개 (성공, 유효하지 않은 토큰)
"""

import pytest
from sqlalchemy import select

from app.core.security import create_tokens, decode_token, verify_password
from app.models.user import AuthProvider, User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService


# ===== register 테스트 (3개) =====


@pytest.mark.asyncio
async def test_register_success(db_session):
    """회원가입 성공 테스트"""
    auth_service = AuthService(db_session)

    register_data = RegisterRequest(
        email="new_user@example.com",
        password="test_password123",
        name="신규 사용자",
    )

    result = await auth_service.register(register_data)

    # 사용자 정보 검증
    assert result.user.email == register_data.email
    assert result.user.name == register_data.name
    assert result.user.auth_provider == AuthProvider.LOCAL.value

    # 토큰 생성 검증
    assert result.tokens.access_token is not None
    assert result.tokens.refresh_token is not None
    assert result.tokens.token_type == "Bearer"

    # DB에 저장되었는지 확인
    db_user = await db_session.execute(
        select(User).where(User.email == register_data.email)
    )
    saved_user = db_user.scalar_one_or_none()
    assert saved_user is not None
    assert saved_user.hashed_password is not None


@pytest.mark.asyncio
async def test_register_duplicate_email(db_session, test_user: User):
    """이메일 중복 시 회원가입 실패"""
    auth_service = AuthService(db_session)

    register_data = RegisterRequest(
        email=test_user.email,  # 이미 존재하는 이메일
        password="test_password123",
        name="중복 사용자",
    )

    with pytest.raises(ValueError, match="EMAIL_EXISTS"):
        await auth_service.register(register_data)


@pytest.mark.asyncio
async def test_register_password_hashed(db_session):
    """비밀번호가 해싱되어 저장되는지 확인"""
    auth_service = AuthService(db_session)

    plain_password = "plain_password_123"
    register_data = RegisterRequest(
        email="hash_test@example.com",
        password=plain_password,
        name="해싱 테스트 사용자",
    )

    result = await auth_service.register(register_data)

    # DB에서 사용자 조회
    db_user = await db_session.execute(
        select(User).where(User.email == register_data.email)
    )
    saved_user = db_user.scalar_one_or_none()

    # 비밀번호가 해싱되었는지 확인
    assert saved_user.hashed_password != plain_password
    assert verify_password(plain_password, saved_user.hashed_password) is True


# ===== login 테스트 (4개) =====


@pytest.mark.asyncio
async def test_login_success(db_session):
    """로그인 성공 테스트"""
    auth_service = AuthService(db_session)

    # 먼저 사용자 등록
    register_data = RegisterRequest(
        email="login_test@example.com",
        password="test_password123",
        name="로그인 테스트",
    )
    await auth_service.register(register_data)

    # 로그인 시도
    login_data = LoginRequest(
        email="login_test@example.com",
        password="test_password123",
    )

    result = await auth_service.login(login_data)

    assert result.user.email == login_data.email
    assert result.tokens.access_token is not None
    assert result.tokens.refresh_token is not None


@pytest.mark.asyncio
async def test_login_invalid_email(db_session):
    """존재하지 않는 이메일로 로그인 시도"""
    auth_service = AuthService(db_session)

    login_data = LoginRequest(
        email="nonexistent@example.com",
        password="any_password",
    )

    with pytest.raises(ValueError, match="INVALID_CREDENTIALS"):
        await auth_service.login(login_data)


@pytest.mark.asyncio
async def test_login_invalid_password(db_session):
    """잘못된 비밀번호로 로그인 시도"""
    auth_service = AuthService(db_session)

    # 먼저 사용자 등록
    register_data = RegisterRequest(
        email="password_test@example.com",
        password="correct_password",
        name="비밀번호 테스트",
    )
    await auth_service.register(register_data)

    # 잘못된 비밀번호로 로그인
    login_data = LoginRequest(
        email="password_test@example.com",
        password="wrong_password",
    )

    with pytest.raises(ValueError, match="INVALID_CREDENTIALS"):
        await auth_service.login(login_data)


@pytest.mark.asyncio
async def test_login_generates_valid_tokens(db_session):
    """로그인 시 유효한 토큰 생성 확인"""
    auth_service = AuthService(db_session)

    # 사용자 등록
    register_data = RegisterRequest(
        email="token_test@example.com",
        password="test_password123",
        name="토큰 테스트",
    )
    register_result = await auth_service.register(register_data)

    # 로그인
    login_data = LoginRequest(
        email="token_test@example.com",
        password="test_password123",
    )
    login_result = await auth_service.login(login_data)

    # access_token 검증
    access_payload = decode_token(login_result.tokens.access_token)
    assert access_payload is not None
    assert access_payload.get("type") == "access"
    assert access_payload.get("sub") == str(register_result.user.id)

    # refresh_token 검증
    refresh_payload = decode_token(login_result.tokens.refresh_token)
    assert refresh_payload is not None
    assert refresh_payload.get("type") == "refresh"
    assert refresh_payload.get("sub") == str(register_result.user.id)


# ===== get_user_by_email 테스트 (2개) =====


@pytest.mark.asyncio
async def test_get_user_by_email_success(db_session, test_user: User):
    """이메일로 사용자 조회 성공"""
    auth_service = AuthService(db_session)

    found_user = await auth_service.get_user_by_email(test_user.email)

    assert found_user is not None
    assert found_user.id == test_user.id
    assert found_user.email == test_user.email
    assert found_user.name == test_user.name


@pytest.mark.asyncio
async def test_get_user_by_email_not_found(db_session):
    """존재하지 않는 이메일 조회 시 None 반환"""
    auth_service = AuthService(db_session)

    found_user = await auth_service.get_user_by_email("nonexistent@example.com")

    assert found_user is None


# ===== get_user_by_id 테스트 (2개) =====


@pytest.mark.asyncio
async def test_get_user_by_id_success(db_session, test_user: User):
    """ID로 사용자 조회 성공"""
    auth_service = AuthService(db_session)

    found_user = await auth_service.get_user_by_id(str(test_user.id))

    assert found_user is not None
    assert found_user.id == test_user.id
    assert found_user.email == test_user.email


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(db_session):
    """존재하지 않는 ID 조회 시 None 반환"""
    auth_service = AuthService(db_session)
    from uuid import uuid4

    fake_id = str(uuid4())
    found_user = await auth_service.get_user_by_id(fake_id)

    assert found_user is None


# ===== refresh_token 테스트 (2개) =====


@pytest.mark.asyncio
async def test_refresh_token_success(db_session, test_user: User):
    """토큰 갱신 성공"""
    auth_service = AuthService(db_session)

    # refresh_token 생성
    tokens = create_tokens(str(test_user.id))
    refresh_token = tokens["refresh_token"]

    # 토큰 갱신
    new_tokens = await auth_service.refresh_token(refresh_token)

    assert new_tokens.access_token is not None
    assert new_tokens.refresh_token is not None
    assert new_tokens.token_type == "Bearer"

    # 토큰 페이로드 검증 (user_id가 동일해야 함)
    new_payload = decode_token(new_tokens.access_token)
    assert new_payload.get("sub") == str(test_user.id)
    assert new_payload.get("type") == "access"


@pytest.mark.asyncio
async def test_refresh_token_invalid(db_session):
    """유효하지 않은 refresh_token으로 갱신 시도"""
    auth_service = AuthService(db_session)

    invalid_token = "invalid.token.here"

    with pytest.raises(ValueError, match="INVALID_TOKEN"):
        await auth_service.refresh_token(invalid_token)


# ===== get_current_user 테스트 (2개) =====


@pytest.mark.asyncio
async def test_get_current_user_success(db_session, test_user: User):
    """현재 사용자 조회 성공"""
    auth_service = AuthService(db_session)

    # access_token 생성
    tokens = create_tokens(str(test_user.id))
    access_token = tokens["access_token"]

    # 현재 사용자 조회
    current_user = await auth_service.get_current_user(access_token)

    assert current_user is not None
    assert current_user.id == test_user.id
    assert current_user.email == test_user.email


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session):
    """유효하지 않은 access_token으로 조회 시도"""
    auth_service = AuthService(db_session)

    invalid_token = "invalid.access.token"

    with pytest.raises(ValueError, match="INVALID_TOKEN"):
        await auth_service.get_current_user(invalid_token)
