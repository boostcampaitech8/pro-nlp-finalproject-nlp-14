# Mit

회의 기반 조직 지식 시스템

## 빠른 시작

```bash
# 1. 의존성 설치
make install

# 2. 환경변수 설정
cp .env.dev.example .env
# .env에 DB, OAuth 등 입력

# 3. k3d 인프라 세팅
make k8s-setup     # 클러스터 생성 (최초 1회)
make k8s-infra     # Redis, LiveKit 배포
make k8s-build-worker
make k8s-pf        # 포트 포워딩

# 4. 개발 서버
make dev
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API 문서: http://localhost:8000/docs

k8s 세부 설정은 [k8s/README.md](k8s/README.md) 참고.
k3s 실제 production 배포 시 [deploy-prod.sh](k8s/deploy-prod.sh) 참고.

## 환경변수

```bash
# DB (외부 - 개발 시에도 외부 디비 사용)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_PASSWORD=

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

## 주요 명령어

```bash
# 개발
make dev              # FE + BE 실행
make dev-fe           # Frontend만
make dev-be           # Backend만

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
    ├── charts/mit/           # Helm 차트
    ├── scripts/              # 배포 스크립트
    └── values/               # 환경별 설정
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
