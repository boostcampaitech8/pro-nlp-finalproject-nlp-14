from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_auth_service
from app.core.database import get_db
from app.schemas import (
    AuthResponse,
    ErrorResponse,
    GoogleLoginUrlResponse,
    NaverLoginUrlResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth.auth_service import AuthService
from app.services.auth.google_oauth_service import GoogleOAuthService
from app.services.auth.guest_auth_service import GuestAuthService
from app.services.auth.naver_oauth_service import NaverOAuthService

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()

# 세션 기반 state 저장 (프로덕션에서는 Redis 사용 권장)
# 간단한 구현을 위해 메모리 기반으로 처리
_oauth_states: dict[str, bool] = {}


def get_naver_oauth_service(db: AsyncSession = Depends(get_db)) -> NaverOAuthService:
    """네이버 OAuth 서비스 의존성"""
    return NaverOAuthService(db)


def get_google_oauth_service(db: AsyncSession = Depends(get_db)) -> GoogleOAuthService:
    """Google OAuth 서비스 의존성"""
    return GoogleOAuthService(db)


def get_guest_auth_service(db: AsyncSession = Depends(get_db)) -> GuestAuthService:
    """게스트 인증 서비스 의존성"""
    return GuestAuthService(db)


@router.get(
    "/naver/login",
    response_model=NaverLoginUrlResponse,
)
async def get_naver_login_url(
    naver_service: Annotated[NaverOAuthService, Depends(get_naver_oauth_service)],
) -> NaverLoginUrlResponse:
    """네이버 OAuth 로그인 URL 반환"""
    state = naver_service.generate_state()
    _oauth_states[state] = True  # state 저장
    url = naver_service.get_authorization_url(state)
    return NaverLoginUrlResponse(url=url)


@router.get(
    "/naver/callback",
    response_model=AuthResponse,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def naver_callback(
    code: Annotated[str, Query(description="네이버 인증 코드")],
    state: Annotated[str, Query(description="CSRF 방지용 상태 토큰")],
    naver_service: Annotated[NaverOAuthService, Depends(get_naver_oauth_service)],
) -> AuthResponse:
    """네이버 OAuth 콜백 처리"""
    # state 검증
    if state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_STATE", "message": "Invalid or expired state token"},
        )

    # 사용한 state 삭제
    del _oauth_states[state]

    try:
        return await naver_service.authenticate(code, state)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_FAILED", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_FAILED", "message": f"Authentication failed: {str(e)}"},
        )


@router.get(
    "/google/login",
    response_model=GoogleLoginUrlResponse,
)
async def get_google_login_url(
    google_service: Annotated[GoogleOAuthService, Depends(get_google_oauth_service)],
) -> GoogleLoginUrlResponse:
    """Google OAuth 로그인 URL 반환"""
    state = google_service.generate_state()
    _oauth_states[state] = True  # state 저장
    url = google_service.get_authorization_url(state)
    return GoogleLoginUrlResponse(url=url)


@router.get(
    "/google/callback",
    response_model=AuthResponse,
    response_model_by_alias=True,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def google_callback(
    code: Annotated[str, Query(description="Google 인증 코드")],
    state: Annotated[str, Query(description="CSRF 방지용 상태 토큰")],
    google_service: Annotated[GoogleOAuthService, Depends(get_google_oauth_service)],
) -> AuthResponse:
    """Google OAuth 콜백 처리"""
    # state 검증
    if state not in _oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_STATE", "message": "Invalid or expired state token"},
        )

    # 사용한 state 삭제
    del _oauth_states[state]

    try:
        return await google_service.authenticate(code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_FAILED", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_FAILED", "message": f"Authentication failed: {str(e)}"},
        )


@router.post(
    "/guest",
    response_model=AuthResponse,
    response_model_by_alias=True,
    responses={
        500: {"model": ErrorResponse},
    },
)
async def guest_login(
    guest_service: Annotated[GuestAuthService, Depends(get_guest_auth_service)],
) -> AuthResponse:
    """게스트 로그인 - 즉시 게스트 계정 생성 및 토큰 발급"""
    try:
        return await guest_service.authenticate()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "GUEST_LOGIN_FAILED", "message": f"Guest login failed: {str(e)}"},
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    response_model_by_alias=True,
    responses={401: {"model": ErrorResponse}},
)
async def refresh_token(
    data: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """토큰 갱신"""
    try:
        return await auth_service.refresh_token(data.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "message": "Invalid or expired refresh token"},
        )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
)
async def logout(
    _credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> None:
    """로그아웃 (현재는 클라이언트 측 토큰 삭제만 필요)"""
    # TODO: Redis에 refresh token 블랙리스트 추가
    return None


@router.get(
    "/me",
    response_model=UserResponse,
    response_model_by_alias=True,
    responses={401: {"model": ErrorResponse}},
)
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    """현재 사용자 정보"""
    try:
        user = await auth_service.get_current_user(credentials.credentials)
        return UserResponse.model_validate(user)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )
