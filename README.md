# Mit

Git이 코드의 진실을 관리하듯, **조직 회의의 진실을 관리하는** 협업 기반 조직 지식 시스템

## 프로젝트 구조

```
mit/
├── api-contract/           # API 명세 (OpenAPI 3.0) - SSOT
├── packages/shared-types/  # FE/BE 공유 타입 (자동 생성)
├── frontend/               # React + TypeScript + Vite
├── backend/                # FastAPI + Python 3.11 + uv
├── docker/                 # Docker Compose
└── Makefile                # 편의 명령어
```

---

## 시작하기

### 사전 요구사항

- Node.js 20+
- pnpm 9+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python 패키지 관리)
- Docker & Docker Compose

### 설치 (Makefile 사용)

```bash
# 전체 설치
make install

# 인프라 실행 (PostgreSQL, Redis, MinIO)
make infra-up

# DB 마이그레이션
make db-migrate m="create users table"
make db-upgrade

# 개발 서버 실행
make dev
```

### 수동 설치

```bash
# 1. Node.js 의존성
pnpm install
pnpm --filter @mit/shared-types build

# 2. Backend 의존성 (uv)
cd backend && uv sync && cd ..

# 3. 환경변수 설정
cp backend/.env.example backend/.env

# 4. 인프라 실행
make infra-up

# 5. DB 마이그레이션
cd backend
uv run alembic revision --autogenerate -m "create users table"
uv run alembic upgrade head
```

---

## Makefile 명령어

```bash
make help              # 전체 명령어 보기

# 개발 (로컬)
make install           # 의존성 설치
make dev               # FE + BE 로컬 실행
make dev-fe            # Frontend만
make dev-be            # Backend만

# Docker
make infra-up          # 인프라만 (DB, Redis, MinIO)
make docker-up         # 전체 (infra + backend)
make docker-down       # 전체 중지
make docker-logs       # 로그 보기
make docker-rebuild    # Backend 이미지 재빌드

# DB 마이그레이션
make db-migrate m="설명"  # 마이그레이션 생성
make db-upgrade           # 마이그레이션 적용
make db-downgrade         # 롤백

# 빌드
make build             # Frontend 프로덕션 빌드
make clean             # 빌드 아티팩트 정리
```

---

## 개발 서버

```bash
make dev
# 또는
make dev-fe   # Frontend: http://localhost:5173
make dev-be   # Backend:  http://localhost:8000
```

---

## Frontend

### 기술 스택

| 기술 | 용도 |
|------|------|
| React 18 | UI 프레임워크 |
| TypeScript 5 | 타입 안전성 |
| Vite 6 | 빌드 도구 |
| Tailwind CSS 3 | 스타일링 |
| Zustand 5 | 상태 관리 |
| React Router 7 | 라우팅 |
| Axios | HTTP 클라이언트 |

### 환경변수

```bash
# frontend/.env.example
VITE_API_URL=           # 비워두면 /api/v1 (Vite 프록시)
```

---

## Backend

### 기술 스택

| 기술 | 용도 |
|------|------|
| FastAPI | 웹 프레임워크 |
| Python 3.11+ | 런타임 |
| uv | 패키지 관리 |
| SQLAlchemy 2.0 | ORM (async) |
| PostgreSQL 15 | 데이터베이스 |
| Redis 7 | 캐시, 세션 |
| Alembic | DB 마이그레이션 |

### 명령어 (uv)

```bash
cd backend

# 의존성
uv sync                # 설치
uv add <package>       # 추가
uv add --dev <package> # 개발용 추가

# 실행
uv run uvicorn app.main:app --reload --port 8000

# 마이그레이션
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "설명"

# 테스트/린트
uv run pytest
uv run ruff check .
```

### 환경변수

```bash
# backend/.env.example
APP_ENV=development
DEBUG=false
HOST=0.0.0.0
PORT=8000
DATABASE_URL=postgresql+asyncpg://mit:mitpassword@localhost:5432/mit
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change-this-secret-key
CORS_ORIGINS=http://localhost:5173,http://localhost:4040
```

### API 문서

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Docker

### 서비스

| 서비스 | 포트 | 용도 |
|--------|------|------|
| PostgreSQL | 5432 | 데이터베이스 |
| Redis | 6379 | 캐시, 세션 |
| MinIO | 9000, 9001 | 파일 스토리지 |
| Backend | 3000 | API 서버 (프로덕션) |

### 환경변수

```bash
# docker/.env.example 참고
cp docker/.env.example docker/.env
# JWT_SECRET_KEY 등 수정
```

---

## 프로덕션 배포

### 서버 구성

| 서비스 | URL |
|--------|-----|
| Frontend | `http://meetmit.duckdns.org:4040` |
| Backend | `http://meetmit.duckdns.org:3000` |

### Backend 배포 (Docker)

```bash
# 1. 환경변수 설정
cp docker/.env.example docker/.env
# docker/.env 수정:
#   JWT_SECRET_KEY=<openssl rand -hex 32>
#   CORS_ORIGINS=http://meetmit.duckdns.org:4040

# 2. 실행
make docker-up

# 3. 마이그레이션 (최초 1회)
make db-upgrade
```

### Frontend 배포

```bash
# 1. 환경변수 설정
cp frontend/.env.production.example frontend/.env.production
# VITE_API_URL=http://meetmit.duckdns.org:3000/api/v1

# 2. 빌드
make build

# 3. 서빙 (포트 4040)
cd frontend && npx serve -s dist -l 4040
```

---

## API Contract

API 명세: `api-contract/openapi.yaml`

### 인증 API

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/auth/register | 회원가입 |
| POST | /api/v1/auth/login | 로그인 |
| POST | /api/v1/auth/refresh | 토큰 갱신 |
| POST | /api/v1/auth/logout | 로그아웃 |
| GET | /api/v1/auth/me | 현재 사용자 |

### 타입 생성

```bash
pnpm run generate:types
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
- DB 테이블/컬럼: snake_case

---

## 라이선스

Private
