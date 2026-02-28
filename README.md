# Mit

회의 기반 조직 지식 시스템

## 빠른 시작

```bash
# 1. 의존성 설치
make install

# 2. 환경변수 설정
cp .env.dev.example .env
# .env에 OAuth 등 입력

# 3. 인프라 준비 (로컬 DB + k3d Redis/LiveKit + worker 이미지)
make infra

# 또는 수동 단계 실행 시:
make dev-db-up     # PostgreSQL, Neo4j

# 4. k3d 인프라 세팅
make k8s-setup     # 클러스터 생성 (최초 1회)
make k8s-infra     # Redis, LiveKit 배포
make k8s-build-worker
make k8s-pf        # 포트 포워딩

# 5. 개발 서버
make dev
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API 문서: http://localhost:8000/docs

k8s 세부 설정은 [k8s/README.md](k8s/README.md) 참고.

## 배포 모델

- `prod`: Argo CD `ApplicationSet` GitOps (`k8s/argocd/**`)
- `local`: `make infra`, `make dev` 중심 개발 흐름 유지
- CI는 이미지를 빌드하고 `k8s/image-tags.yaml`을 갱신하며, prod 배포는 Argo auto sync로 반영
- Secret SSOT
  - `prod`: GCP Secret Manager + ESO -> `Secret/mit-secrets`
  - `local`: `k8s/scripts/sync-app-secret.sh`

## 환경변수

```bash
# DB (로컬 Docker: ./docker/db)
DATABASE_URL=postgresql+asyncpg://mit:<POSTGRES_PASSWORD>@localhost:5432/mit
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=
REDIS_URL=redis://localhost:6379/0
ARQ_REDIS_URL=redis://localhost:6379/1

# OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

# LiveKit (로컬)
LIVEKIT_API_KEY=mit-api-key
LIVEKIT_API_SECRET=secret-change-in-production-min-32-chars
LIVEKIT_WS_URL=ws://localhost:7880

# AI
NCP_CLOVASTUDIO_API_KEY=
```

`make infra` + `make dev` 조합에서는 DB 관련 변수(`DATABASE_URL`, `NEO4J_*`)를 비워둬도 `docker/db` 기본값으로 자동 주입됩니다.

## 주요 명령어

```bash
# 개발
make dev              # FE + BE + ARQ 실행
make dev-fe           # Frontend만
make dev-be           # Backend만
make dev-arq          # ARQ Worker만
make dev-db-up        # 로컬 PostgreSQL/Neo4j 시작
make dev-db-down      # 로컬 PostgreSQL/Neo4j 중지
make infra            # DB + k3d 인프라 일괄 시작

# k8s
make k8s-status       # Pod 상태
make k8s-logs svc=backend
make k8s-push-be      # Backend 재배포
make k8s-push-fe      # Frontend 재배포

# DB
make db-migrate m="설명"
make db-upgrade
```

## 프로젝트 구조

```
mit/
├── api-contract/             # OpenAPI 명세 (SSOT)
│   ├── openapi.yaml          # 메인 진입점
│   ├── schemas/              # 스키마 정의
│   │   ├── common.yaml       # 공통 타입 (UUID, Timestamp)
│   │   ├── auth.yaml         # 인증
│   │   ├── team.yaml         # 팀 + 멤버
│   │   ├── meeting.yaml      # 회의 + 참여자
│   │   └── webrtc.yaml       # WebRTC
│   └── paths/                # 엔드포인트 정의
│
├── packages/shared-types/    # FE/BE 공유 타입 (자동 생성)
│
├── frontend/                 # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/       # UI 컴포넌트
│   │   ├── pages/            # 페이지
│   │   ├── stores/           # Zustand 스토어
│   │   ├── services/         # API 클라이언트
│   │   └── hooks/            # Custom hooks
│   └── nginx.conf            # SPA 라우팅 + API 프록시
│
├── backend/                  # FastAPI + Python 3.11 + uv
│   ├── app/
│   │   ├── api/v1/           # API 엔드포인트
│   │   ├── models/           # SQLAlchemy 모델
│   │   ├── schemas/          # Pydantic 스키마
│   │   ├── services/         # 비즈니스 로직
│   │   └── infrastructure/   # 외부 연동 (Graph 등)
│   ├── alembic/              # DB 마이그레이션
│   ├── neo4j/                # Neo4j 스키마
│   └── worker/               # Realtime Worker (LiveKit)
│
└── k8s/                      # Kubernetes 배포
    ├── charts/mit/           # 앱 전용 Helm 차트 (backend/frontend/arq)
    ├── charts/cloudflared/   # Cloudflare Tunnel Helm 차트
    ├── argocd/               # AppProject/ApplicationSet/root app
    ├── scripts/              # 배포 스크립트
    └── image-tags.yaml       # CI 이미지 태그 SSOT
```

## API

API 명세: `api-contract/openapi.yaml`

### 인증

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/auth/register | 회원가입 |
| POST | /api/v1/auth/login | 로그인 |
| POST | /api/v1/auth/refresh | 토큰 갱신 |
| POST | /api/v1/auth/logout | 로그아웃 |
| GET | /api/v1/auth/me | 현재 사용자 |

### 팀

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/teams | 팀 목록 |
| POST | /api/v1/teams | 팀 생성 |
| GET | /api/v1/teams/{id} | 팀 상세 |
| PATCH | /api/v1/teams/{id} | 팀 수정 |
| DELETE | /api/v1/teams/{id} | 팀 삭제 |
| GET | /api/v1/teams/{id}/members | 멤버 목록 |
| POST | /api/v1/teams/{id}/members | 멤버 초대 |
| PATCH | /api/v1/teams/{id}/members/{userId} | 멤버 역할 변경 |
| DELETE | /api/v1/teams/{id}/members/{userId} | 멤버 제거 |

### 회의

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/meetings | 회의 목록 |
| POST | /api/v1/meetings | 회의 생성 |
| GET | /api/v1/meetings/{id} | 회의 상세 |
| PATCH | /api/v1/meetings/{id} | 회의 수정 |
| DELETE | /api/v1/meetings/{id} | 회의 삭제 |
| GET | /api/v1/meetings/{id}/participants | 참여자 목록 |
| POST | /api/v1/meetings/{id}/participants | 참여자 추가 |

### WebRTC

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/meetings/{id}/room | 회의실 정보 |
| POST | /api/v1/meetings/{id}/start | 회의 시작 (host) |
| POST | /api/v1/meetings/{id}/end | 회의 종료 (host) |

### Decision

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/meetings/{id}/decisions | 회의의 Decision 목록 |
| GET | /api/v1/decisions/{id} | Decision 상세 |
| POST | /api/v1/decisions/{id}/reviews | 리뷰 생성 (approve/reject) |

### Chat / Agent

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/chat | AI 채팅 |
| POST | /api/v1/agent/query | Agent 쿼리 |
