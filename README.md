# Mit

Git이 코드의 진실을 관리하듯, **조직 회의의 진실을 관리하는** 협업 기반 조직 지식 시스템

## 프로젝트 구조

```
mit/
├── api-contract/           # API 명세 (OpenAPI 3.0) - Single Source of Truth
│   ├── openapi.yaml
│   ├── schemas/
│   └── paths/
├── packages/
│   └── shared-types/       # FE/BE 공유 타입 (OpenAPI에서 자동 생성)
├── frontend/               # React + TypeScript + Vite
├── backend/                # FastAPI + Python 3.11
└── docker/                 # Docker Compose (PostgreSQL, Redis, MinIO)
```

---

## 시작하기

### 사전 요구사항

- Node.js 20+
- pnpm 9+
- Python 3.11+
- uv (Python 패키지 관리)
- Docker & Docker Compose

### 설치

```bash
# 1. 저장소 클론
git clone <repository-url>
cd mit

# 2. Node.js 의존성 설치
pnpm install

# 3. shared-types 빌드
pnpm --filter @mit/shared-types build

# 4. Backend 의존성 설치 (uv가 자동으로 가상환경 생성)
cd backend
uv sync
cd ..

# 5. Docker 서비스 실행 (PostgreSQL, Redis, MinIO)
pnpm run docker:up

# 6. DB 마이그레이션
cd backend
alembic upgrade head
cd ..
```

### 개발 서버 실행

```bash
# FE + BE 동시 실행
pnpm run dev

# 또는 개별 실행
pnpm run dev:fe   # Frontend (http://localhost:5173)
pnpm run dev:be   # Backend  (http://localhost:8000)
```

---

## Frontend

### 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| React | 18.x | UI 프레임워크 |
| TypeScript | 5.x | 타입 안전성 |
| Vite | 6.x | 빌드 도구 |
| Tailwind CSS | 3.x | 스타일링 |
| Zustand | 5.x | 상태 관리 |
| React Router | 7.x | 라우팅 |
| Axios | 1.x | HTTP 클라이언트 |

### 디렉토리 구조

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/            # 공통 UI 컴포넌트 (Button, Input)
│   │   └── auth/          # 인증 관련 컴포넌트
│   ├── pages/             # 페이지 컴포넌트
│   ├── hooks/             # 커스텀 훅
│   ├── services/          # API 호출 로직
│   │   ├── api.ts         # Axios 인스턴스 (인터셉터 포함)
│   │   └── authService.ts # 인증 API
│   ├── stores/            # Zustand 스토어
│   │   └── authStore.ts   # 인증 상태 관리
│   └── types/             # 타입 정의 (shared-types re-export)
├── index.html
├── vite.config.ts
├── tailwind.config.js
└── package.json
```

### 명령어

```bash
pnpm --filter frontend dev        # 개발 서버
pnpm --filter frontend build      # 프로덕션 빌드
pnpm --filter frontend typecheck  # 타입 체크
pnpm --filter frontend lint       # 린트
```

### 환경 변수

Vite 프록시 설정으로 `/api` 요청이 자동으로 `http://localhost:8000`으로 전달됩니다.

---

## Backend

### 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| FastAPI | 0.115+ | 웹 프레임워크 |
| Python | 3.11+ | 런타임 |
| uv | - | 패키지 관리 |
| SQLAlchemy | 2.0+ | ORM (비동기) |
| PostgreSQL | 15 | 데이터베이스 |
| Redis | 7 | 캐시, 세션 |
| Alembic | 1.14+ | DB 마이그레이션 |
| python-jose | 3.3+ | JWT 처리 |
| passlib | 1.7+ | 비밀번호 해싱 (bcrypt) |

### 디렉토리 구조

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/  # API 엔드포인트
│   │       │   └── auth.py
│   │       └── router.py   # 라우터 통합
│   ├── core/
│   │   ├── config.py       # 환경 설정 (pydantic-settings)
│   │   ├── database.py     # DB 연결 (async)
│   │   └── security.py     # JWT, 비밀번호 처리
│   ├── models/             # SQLAlchemy 모델
│   │   └── user.py
│   ├── schemas/            # Pydantic 스키마
│   │   ├── auth.py
│   │   └── common.py
│   ├── services/           # 비즈니스 로직
│   │   └── auth_service.py
│   └── main.py             # FastAPI 앱 진입점
├── alembic/                # DB 마이그레이션
│   ├── env.py
│   └── versions/
├── pyproject.toml          # 의존성 정의
├── uv.lock                 # 의존성 잠금 파일
└── .env.example
```

### 명령어

```bash
# 의존성 설치/동기화
cd backend
uv sync                    # 의존성 설치 (가상환경 자동 생성)
uv sync --dev              # dev 의존성 포함

# 개발 서버
uv run uvicorn app.main:app --reload --port 8000

# DB 마이그레이션
uv run alembic upgrade head                        # 마이그레이션 적용
uv run alembic revision --autogenerate -m "설명"   # 마이그레이션 생성

# 테스트 및 린트
uv run pytest
uv run ruff check .
uv run ruff format .

# 의존성 추가
uv add <package>           # 프로덕션 의존성
uv add --dev <package>     # 개발 의존성
```

### 환경 변수

`backend/.env` 파일 생성 (`.env.example` 참고):

```env
DEBUG=false
DATABASE_URL=postgresql+asyncpg://mit:mitpassword@localhost:5432/mit
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-super-secret-key-change-in-production
CORS_ORIGINS=["http://localhost:5173"]
```

### API 문서

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## API Contract

API 명세는 `api-contract/openapi.yaml`에 정의되어 있습니다.

### 인증 API

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/auth/register | 회원가입 |
| POST | /api/v1/auth/login | 로그인 |
| POST | /api/v1/auth/refresh | 토큰 갱신 |
| POST | /api/v1/auth/logout | 로그아웃 |
| GET | /api/v1/auth/me | 현재 사용자 정보 |

### 타입 생성

API 명세 변경 후 타입을 재생성하세요:

```bash
pnpm run generate:types
```

---

## Docker

### 서비스

| 서비스 | 포트 | 용도 |
|--------|------|------|
| PostgreSQL | 5432 | 메인 데이터베이스 |
| Redis | 6379 | 캐시, 세션 |
| MinIO | 9000, 9001 | 파일 스토리지 (S3 호환) |

### 명령어

```bash
pnpm run docker:up    # 서비스 시작
pnpm run docker:down  # 서비스 중지
```

### 접속 정보

```
PostgreSQL: localhost:5432
  - User: mit
  - Password: mitpassword
  - Database: mit

Redis: localhost:6379

MinIO Console: http://localhost:9001
  - User: minioadmin
  - Password: minioadmin
```

---

## 개발 워크플로우

### API 변경 시 (Contract First)

1. `api-contract/openapi.yaml` 수정
2. `pnpm run generate:types` 실행
3. Backend 구현
4. Frontend 구현
5. 한 커밋에 모두 포함

### 코드 스타일

- TypeScript: camelCase (변수), PascalCase (타입/컴포넌트)
- Python: snake_case (변수/함수), PascalCase (클래스)
- API 경로: kebab-case (`/api/v1/meeting-reviews`)
- DB 테이블/컬럼: snake_case (`meeting_reviews`)

---

## 라이선스

Private
