# CLAUDE.md

> 이 파일은 Claude Code가 프로젝트 맥락을 파악하기 위해 읽는 문서입니다.
> 작업 후 진행 상황을 업데이트해주세요.

---

## 프로젝트 개요

**Mit**는 "Git이 코드의 진실을 관리하듯, 조직 회의의 진실을 관리하는" 협업 기반 조직 지식 시스템입니다.

핵심 컨셉:
- 회의록을 PR Review 스타일로 팀원들이 검토/합의
- 합의된 내용만 조직의 Ground Truth(GT)로 확정
- 회의마다 GT가 축적되어 조직 지식 DB 성장

---

## 디렉토리 구조

```
mit/
├── CLAUDE.md                    # (이 파일) AI 컨텍스트
├── Makefile                     # 편의 명령어
├── api-contract/                # API 명세 (SSOT)
│   ├── openapi.yaml
│   ├── schemas/
│   └── paths/
├── packages/
│   └── shared-types/            # FE/BE 공유 타입
├── frontend/                    # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── stores/
│   ├── .env.example
│   └── .env.production.example
├── backend/                     # FastAPI + Python 3.11
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── alembic/
│   ├── pyproject.toml           # uv 의존성 정의
│   ├── uv.lock
│   ├── Dockerfile
│   └── .env.example
├── docker/
│   ├── docker-compose.yml       # infra + backend
│   └── .env.example
├── scripts/
└── docs/
```

---

## 핵심 규칙 (반드시 준수)

### 1. API Contract First
API 변경 시 **반드시** 이 순서로 작업:
```
1. api-contract/openapi.yaml 수정
2. pnpm run generate:types 실행
3. backend 구현
4. frontend 구현
```

### 2. 원자적 변경
API 변경은 명세 + BE + FE를 **한 커밋 또는 한 PR**에서 함께 수정.
절대로 명세만 바꾸고 구현을 나중에 하지 않음.

### 3. 타입 공유
- FE/BE 공통 타입: `packages/shared-types/`
- OpenAPI에서 자동 생성: `pnpm run generate:types`
- 수동으로 타입 중복 정의 금지

### 4. 네이밍 규칙
- API 경로: kebab-case (`/api/v1/meeting-reviews`)
- DB 테이블/컬럼: snake_case (`meeting_reviews`, `created_at`)
- TypeScript: camelCase (변수), PascalCase (타입/컴포넌트)
- Python: snake_case (변수/함수), PascalCase (클래스)

---

## 기술 스택

### Frontend
| 기술 | 용도 |
|------|------|
| React 18 | UI 프레임워크 |
| TypeScript | 타입 안전성 |
| Vite | 빌드 도구 |
| Zustand | 상태 관리 |
| Tailwind CSS | 스타일링 |
| React Router 7 | 라우팅 |
| Axios | HTTP 클라이언트 |

### Backend
| 기술 | 용도 |
|------|------|
| FastAPI | 웹 프레임워크 |
| Python 3.11 | 런타임 |
| uv | 패키지 관리 |
| SQLAlchemy 2.0 | ORM (async) |
| PostgreSQL 15 | 데이터베이스 |
| Redis | 캐시, Pub/Sub |
| Alembic | DB 마이그레이션 |

### WebRTC 아키텍처 (예정)
- **SFU 방식**: 서버가 모든 미디어 스트림 수신 -> 녹음 가능
- aiortc의 `MediaRecorder`로 서버 사이드 녹음
- 시그널링: FastAPI WebSocket

---

## 자주 사용하는 명령어

### Makefile (권장)
```bash
make help              # 전체 명령어 보기

# 개발 (로컬)
make install           # 의존성 설치
make dev               # FE + BE 로컬 실행
make dev-fe            # Frontend만 (http://localhost:5173)
make dev-be            # Backend만 (http://localhost:8000)

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
```

### uv 명령어 (Backend)
```bash
cd backend
uv sync                # 의존성 설치
uv add <package>       # 패키지 추가
uv run uvicorn app.main:app --reload --port 8000
uv run alembic upgrade head
uv run pytest
```

### pnpm 명령어
```bash
pnpm run dev              # FE + BE 동시 실행
pnpm run generate:types   # OpenAPI -> TypeScript 타입 생성
pnpm run typecheck        # 타입 체크
pnpm run lint             # 린트
```

---

## 환경변수 파일

| 파일 | 용도 |
|------|------|
| `docker/.env.example` | 프로덕션 (Docker Compose) |
| `backend/.env.example` | 로컬 개발 |
| `frontend/.env.example` | 로컬 개발 |
| `frontend/.env.production.example` | 프론트엔드 빌드 |

---

## 배포 구성

| 서비스 | URL | 실행 방식 |
|--------|-----|----------|
| Frontend | `http://meetmit.duckdns.org:4040` | serve 또는 nginx |
| Backend | `http://meetmit.duckdns.org:3000` | Docker Compose |

---

## 현재 진행 상황

### Phase 1: 미팅 시스템 (4주)

| 주차 | 기능 | 상태 | 비고 |
|------|------|------|------|
| Week 1 | 프로젝트 초기화 | 완료 | 모노레포, uv, Docker |
| Week 1 | 인증 (로그인/회원가입) | 완료 | JWT 기반 |
| Week 2 | 회의 CRUD | 대기 | |
| Week 2 | 참여자 관리 | 대기 | |
| Week 3 | WebRTC 시그널링 | 대기 | FastAPI WebSocket |
| Week 3 | 실시간 회의 (SFU) | 대기 | aiortc |
| Week 4 | 서버 사이드 녹음 | 대기 | MediaRecorder |
| Week 4 | 회의록 기본 기능 | 대기 | |

### Phase 2: PR Review 시스템 (4주)

| 주차 | 기능 | 상태 | 비고 |
|------|------|------|------|
| Week 5-6 | 회의록 Review UI | 대기 | Comment, Suggestion |
| Week 5-6 | Review API | 대기 | |
| Week 7-8 | Ground Truth 관리 | 대기 | Fact, Branch, History |
| Week 7-8 | Knowledge API | 대기 | |

### Phase 3: 인프라 개선 (2주)

| 주차 | 기능 | 상태 | 비고 |
|------|------|------|------|
| Week 9-10 | 성능 최적화 | 대기 | |
| Week 9-10 | 배포 파이프라인 | 대기 | |

---

## 다음 작업

```
현재 목표: Phase 1 - Week 2 완료

다음 해야 할 작업:
1. [ ] 회의(Meeting) API 명세 작성
2. [ ] 회의 CRUD API 구현 (BE)
3. [ ] 회의 목록/상세 UI 구현 (FE)
4. [ ] 참여자 관리 API 명세 작성
5. [ ] 참여자 관리 API 구현 (BE)
6. [ ] 참여자 관리 UI 구현 (FE)
```

---

## 주의사항

### 코드 스타일
- DO NOT use Emoji.
- 코드의 주석은 한글로 추가한다.

### API 설계
- 모든 목록 API는 페이지네이션 필수 (`page`, `limit`, `total`)
- 에러 응답 형식 통일: `{ error: string, message: string, details?: object }`
- UUID 사용 (auto-increment ID 사용 금지)

### WebRTC
- 순수 P2P 불가 (서버 녹음 필요) -> SFU 아키텍처
- STUN 서버: `stun:stun.l.google.com:19302` (개발용)
- TURN 서버: 프로덕션에서 별도 설정 필요

### 보안
- 비밀번호: bcrypt 해싱
- JWT 만료: access 30분, refresh 7일
- 민감 정보 환경변수로 관리 (.env)

### 파일 업로드
- 녹음 파일: MinIO (S3 호환) 저장
- 최대 파일 크기: 500MB

---

## 참고 문서

- `api-contract/openapi.yaml` - API 명세 (SSOT)
- `README.md` - 설치 및 실행 가이드

---

## 작업 로그

> 작업 완료 시 여기에 기록해주세요.

```
[2024-12-31] Phase 1 - Week 1 완료
- 모노레포 구조 설정 완료 (pnpm workspace)
- Docker Compose 설정 완료 (PostgreSQL, Redis, MinIO, Backend)
- API Contract 작성 완료 (인증 API)
- shared-types 패키지 설정 완료
- Backend 초기화 완료 (FastAPI + SQLAlchemy + JWT + uv)
- Frontend 초기화 완료 (Vite + React + Tailwind + Zustand)
- Makefile 추가 (편의 명령어)
- 프로덕션 배포 설정 (meetmit.duckdns.org:3000/4040)
- 다음: Week 2 - 회의 CRUD 및 참여자 관리
```
