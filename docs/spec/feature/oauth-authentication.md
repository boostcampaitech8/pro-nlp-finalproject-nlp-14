# OAuth 인증 시스템

> 목적: MitHub의 OAuth 기반 사용자 인증 시스템을 설명한다.
> 대상: 기획/개발 전원.
> 범위: Google/Naver OAuth 플로우, 토큰 관리, 사용자 연동.
> 비범위: 인프라 설정, 배포 구성.

---

## 1. 개요

MitHub는 소셜 로그인 기반 인증 시스템을 제공합니다.

### 1.1 지원 프로바이더

| 프로바이더 | 상태 | 스코프 |
|-----------|------|--------|
| Google | ✅ 구현 완료 | `openid email profile` |
| Naver | ✅ 구현 완료 | 기본 프로필 |
| GitHub | ⏳ 예정 | - |

### 1.2 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    OAuth 인증 아키텍처                            │
└─────────────────────────────────────────────────────────────────┘

[Client Browser]
      │
      │ 1. GET /auth/{provider}/login
      ▼
[Backend API]
      │ 2. State 토큰 생성
      │ 3. Authorization URL 반환
      ▼
[OAuth Provider] ─────────────────────────────────┐
      │ 4. 사용자 동의                               │
      ▼                                            │
[Callback URL]                                     │
      │ 5. GET /auth/{provider}/callback?code=xxx  │
      ▼                                            │
[Backend API]                                      │
      │ 6. State 검증                               │
      │ 7. Access Token 교환                       │
      │ 8. 사용자 프로필 조회 ◀───────────────────────┘
      │ 9. 사용자 생성/업데이트
      │ 10. JWT 토큰 발급
      ▼
[Client Browser]
      └─> JWT Access/Refresh Token 저장
```

---

## 2. OAuth 플로우

### 2.1 로그인 시작

```
GET /api/v1/auth/{provider}/login

Response:
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

**생성되는 URL 파라미터:**

| 파라미터 | 설명 |
|----------|------|
| `client_id` | OAuth 앱 클라이언트 ID |
| `redirect_uri` | 콜백 URL (프론트엔드) |
| `response_type` | `code` (Authorization Code Flow) |
| `scope` | 요청 권한 범위 |
| `state` | CSRF 방지 토큰 (32 bytes, URL-safe) |
| `access_type` | `offline` (Google: Refresh Token 요청) |
| `prompt` | `consent` (Google: 매번 동의 화면) |

### 2.2 콜백 처리

```
GET /api/v1/auth/{provider}/callback?code=xxx&state=yyy

Response:
{
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "name": "사용자 이름",
    "auth_provider": "google"
  },
  "tokens": {
    "access_token": "jwt-access-token",
    "refresh_token": "jwt-refresh-token",
    "token_type": "bearer"
  }
}
```

**처리 순서:**
1. State 토큰 검증 (CSRF 방지)
2. Authorization Code → Access Token 교환
3. Access Token → 사용자 프로필 조회
4. 사용자 생성 또는 업데이트
5. JWT 토큰 발급 (Access + Refresh)
6. Neo4j 사용자 동기화

### 2.3 토큰 갱신

```
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "jwt-refresh-token"
}

Response:
{
  "access_token": "new-jwt-access-token",
  "refresh_token": "new-jwt-refresh-token",
  "token_type": "bearer"
}
```

---

## 3. 프로바이더별 구현

### 3.1 Google OAuth

**엔드포인트:**
| 용도 | URL |
|------|-----|
| Authorization | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token | `https://oauth2.googleapis.com/token` |
| UserInfo | `https://openidconnect.googleapis.com/v1/userinfo` |

**프로필 응답 필드:**
```json
{
  "sub": "google-user-id",    // Provider ID로 사용
  "email": "user@gmail.com",
  "name": "사용자 이름",
  "picture": "profile-image-url"
}
```

### 3.2 Naver OAuth

**엔드포인트:**
| 용도 | URL |
|------|-----|
| Authorization | `https://nid.naver.com/oauth2.0/authorize` |
| Token | `https://nid.naver.com/oauth2.0/token` |
| UserInfo | `https://openapi.naver.com/v1/nid/me` |

**프로필 응답 필드:**
```json
{
  "response": {
    "id": "naver-user-id",    // Provider ID로 사용
    "email": "user@naver.com",
    "name": "사용자 이름",
    "profile_image": "profile-image-url"
  }
}
```

---

## 4. 토큰 관리

### 4.1 JWT 토큰 구조

**Access Token:**
```json
{
  "sub": "user-uuid",
  "exp": 1234567890,
  "type": "access"
}
```

**Refresh Token:**
```json
{
  "sub": "user-uuid",
  "exp": 1234567890,
  "type": "refresh"
}
```

### 4.2 토큰 만료 시간

| 토큰 타입 | 만료 시간 | 환경 변수 |
|-----------|-----------|-----------|
| Access Token | 30분 | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Refresh Token | 30일 | `REFRESH_TOKEN_EXPIRE_DAYS` |

### 4.3 State 토큰 관리

**현재 구현:**
- 메모리 딕셔너리에 저장 (`_oauth_states`)
- 단일 사용 후 삭제

**프로덕션 권장:**
- Redis 기반 저장 (TTL 5분)
- 분산 환경 대응

---

## 5. 사용자 연동

### 5.1 사용자 생성/업데이트 플로우

```
OAuth 프로필 수신
        │
        ▼
┌─────────────────────┐
│ provider_id로 검색   │
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
   있음         없음
    │           │
    ▼           ▼
[프로필    ┌─────────────────────┐
 업데이트] │ email로 기존 사용자 검색│
    │     └─────────┬───────────┘
    │               │
    │         ┌─────┴─────┐
    │         │           │
    │        있음         없음
    │         │           │
    │         ▼           ▼
    │    [Provider    [신규 사용자
    │     연결]        생성]
    │         │           │
    └─────────┼───────────┘
              │
              ▼
       [Neo4j 동기화]
```

### 5.2 계정 연결

동일 이메일로 다른 프로바이더 로그인 시:
- 기존 계정에 새 프로바이더 연결
- `auth_provider` 필드 업데이트
- `provider_id` 필드 업데이트

---

## 6. 환경 설정

### 6.1 필수 환경 변수

```bash
# Google OAuth
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback

# Naver OAuth
NAVER_CLIENT_ID=xxx
NAVER_CLIENT_SECRET=xxx
NAVER_REDIRECT_URI=http://localhost:3000/auth/naver/callback

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
```

### 6.2 프론트엔드 콜백 처리

```typescript
// /auth/{provider}/callback 페이지
const code = searchParams.get('code');
const state = searchParams.get('state');

const response = await fetch(`/api/v1/auth/${provider}/callback`, {
  method: 'GET',
  params: { code, state }
});

const { user, tokens } = response.data;
// Access Token 저장 (localStorage 또는 httpOnly Cookie)
```

---

## 7. 에러 처리

| 에러 코드 | 원인 | 해결 방법 |
|-----------|------|-----------|
| `INVALID_STATE` | State 토큰 불일치 | 로그인 재시도 |
| `AUTH_FAILED` | OAuth 인증 실패 | 로그인 재시도 |
| `INVALID_TOKEN` | JWT 검증 실패 | 토큰 갱신 또는 재로그인 |
| `USER_NOT_FOUND` | 사용자 조회 실패 | 재로그인 |

---

## 8. API 엔드포인트 요약

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/auth/{provider}/login` | OAuth 인증 URL 반환 |
| GET | `/auth/{provider}/callback` | OAuth 콜백 처리 |
| POST | `/auth/refresh` | 토큰 갱신 |
| POST | `/auth/logout` | 로그아웃 |
| GET | `/auth/me` | 현재 사용자 정보 |

---

## 9. 보안 고려사항

### 9.1 구현된 보안 기능

- [x] CSRF 방지 (State 토큰)
- [x] PKCE 미지원 (Authorization Code Flow 사용)
- [x] JWT HS256 서명
- [x] 단일 사용 State 토큰

### 9.2 프로덕션 권장 사항

- [ ] Redis 기반 State 저장
- [ ] Refresh Token Rotation
- [ ] Rate Limiting
- [ ] IP 기반 세션 검증

---

## 참조

- 워크플로우 명세: [02-workflow-spec.md](../usecase/02-workflow-spec.md)
- 도메인 모델: [02-conceptual-model.md](../domain/02-conceptual-model.md)
