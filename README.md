# Mit

Git이 코드의 진실을 관리하듯, **조직 회의의 진실을 관리하는** 협업 기반 조직 지식 시스템

## 목차

- [프로젝트 구조](#프로젝트-구조)
- [빠른 시작](#빠른-시작)
- [초기 설정 가이드](#초기-설정-가이드)
- [Makefile 명령어](#makefile-명령어)
- [개발 서버](#개발-서버)
- [Frontend](#frontend)
- [Backend](#backend)
- [Docker](#docker)
- [프로덕션 배포](#프로덕션-배포)
- [API 목록](#api-목록)
- [트러블슈팅](#트러블슈팅)

---

## 프로젝트 구조

```
mit/
├── api-contract/           # API 명세 (OpenAPI 3.0) - SSOT
│   ├── openapi.yaml        # 메인 진입점
│   ├── schemas/            # 스키마 정의
│   │   ├── common.yaml     # 공통 타입 (UUID, Timestamp, PaginationMeta)
│   │   ├── auth.yaml       # 인증 스키마
│   │   ├── team.yaml       # 팀 + 팀멤버 스키마
│   │   ├── meeting.yaml    # 회의 + 참여자 스키마
│   │   ├── webrtc.yaml     # WebRTC 스키마
│   │   └── recording.yaml  # 녹음 스키마
│   └── paths/              # 엔드포인트 정의
├── packages/shared-types/  # FE/BE 공유 타입 (자동 생성)
├── frontend/               # React + TypeScript + Vite
│   ├── Dockerfile          # nginx 기반 프로덕션 이미지
│   └── nginx.conf          # SPA 라우팅 + API 프록시
├── backend/                # FastAPI + Python 3.11 + uv
│   ├── alembic/            # DB 마이그레이션
│   └── Dockerfile          # 프로덕션 이미지
├── docker/                 # Docker Compose
└── Makefile                # 편의 명령어
```

---

## 빠른 시작

```bash
# 1. 의존성 설치
make install

# 2. 인프라 실행 (PostgreSQL, Redis, MinIO)
make infra-up

# 3. DB 마이그레이션
make db-upgrade

# 4. 개발 서버 실행
make dev
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API 문서: http://localhost:8000/docs

---

## 초기 설정 가이드

처음 프로젝트를 시작할 때 아래 단계를 순서대로 진행하세요.

### 1. 사전 요구사항 설치

| 도구 | 버전 | 설치 방법 |
|------|------|----------|
| Node.js | 20+ | https://nodejs.org |
| pnpm | 9+ | `npm install -g pnpm` |
| Python | 3.11+ | https://python.org |
| uv | 최신 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | 최신 | https://docker.com |

### 2. 저장소 클론

```bash
git clone <repository-url>
cd mit
```

### 3. 환경변수 설정

```bash
# Backend 환경변수
cp backend/.env.example backend/.env

# Docker 환경변수 (Docker로 실행 시)
cp docker/.env.example docker/.env
```

**backend/.env 주요 설정:**
```bash
# 데이터베이스 (로컬 개발 시 Docker 인프라 사용)
DATABASE_URL=postgresql+asyncpg://mit:mitpassword@localhost:5432/mit

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT 시크릿 (프로덕션에서는 반드시 변경)
JWT_SECRET_KEY=change-this-secret-key

# CORS 허용 출처
CORS_ORIGINS=["http://localhost:3000"]
```

### 4. 의존성 설치

```bash
# 전체 설치 (권장)
make install

# 또는 수동 설치
pnpm install                           # Node.js 의존성
pnpm --filter @mit/shared-types build  # 공유 타입 빌드
cd backend && uv sync && cd ..         # Python 의존성
```

### 5. 인프라 실행 (Docker)

```bash
# PostgreSQL, Redis, MinIO, Neo4j 실행
make infra-up

# 실행 확인
docker ps
```

| 서비스 | 포트 | 용도 |
|--------|------|------|
| PostgreSQL | 5432 | 데이터베이스 |
| Redis | 6379 | 캐시, 세션 |
| MinIO | 9000, 9001 | 파일 스토리지 |
| Neo4j | 7474, 7687 | 그래프 DB |

### 6. 데이터베이스 초기화

```bash
# 마이그레이션 적용 (테이블 생성)
make db-upgrade

# 또는 수동 실행
cd backend
uv run alembic upgrade head
```

**마이그레이션 명령어:**
```bash
# 새 마이그레이션 생성 (모델 변경 후)
make db-migrate m="add user table"

# 마이그레이션 적용
make db-upgrade

# 마이그레이션 롤백
make db-downgrade

# 마이그레이션 이력 확인
cd backend && uv run alembic history
```

### 7. 개발 서버 실행

```bash
# Frontend + Backend 동시 실행
make dev

# 또는 개별 실행
make dev-fe   # Frontend: http://localhost:3000
make dev-be   # Backend:  http://localhost:8000
```

### 8. 정상 동작 확인

```bash
# Backend 헬스 체크
curl http://localhost:8000/health

# API 문서 확인
open http://localhost:8000/docs

# Frontend 접속
open http://localhost:3000
```

---

## Makefile 명령어

```bash
make help              # 전체 명령어 보기

# 개발 (로컬)
make install           # 의존성 설치
make dev               # FE + BE 로컬 실행
make dev-fe            # Frontend만 (http://localhost:3000)
make dev-be            # Backend만 (http://localhost:8000)

# 테스트
make test-fe           # Frontend 테스트

# Docker (전체)
make docker-up         # 전체 (infra + frontend + backend)
make docker-down       # 전체 중지
make docker-logs       # 로그 보기
make docker-build      # 이미지 빌드
make docker-rebuild    # 이미지 재빌드 (no cache)

# Docker (선택적)
make infra-up          # 인프라만 (DB, Redis, MinIO, Neo4j)
make backend-up        # Backend만
make backend-logs      # Backend 로그
make frontend-up       # Frontend만
make frontend-logs     # Frontend 로그

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
make dev-fe   # Frontend: http://localhost:3000
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

### 명령어

```bash
cd frontend

pnpm dev          # 개발 서버
pnpm build        # 프로덕션 빌드
pnpm preview      # 빌드 미리보기
pnpm lint         # ESLint
pnpm typecheck    # 타입 체크
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

### 주요 모듈

| 모듈 | 역할 |
|------|------|
| `api/dependencies.py` | 공유 의존성 (인증, 회의 검증) |
| `core/constants.py` | 애플리케이션 상수 |
| `services/recording_service.py` | 녹음 비즈니스 로직 |
| `handlers/websocket_message_handlers.py` | WebSocket 메시지 핸들러 |
| `services/webrtc/` | WebRTC 관련 서비스 (연결, 저장) |
| `utils/ice_parser.py` | ICE candidate 파싱 |

### 설계 패턴

- **Strategy Pattern**: WebSocket 메시지 타입별 핸들러 분리
- **Composition**: RecordingSession을 WebRTC 연결 + 저장으로 분리
- **Service Layer**: Endpoint와 비즈니스 로직 분리
- **Shared Dependencies**: 공통 인증/검증 코드 중앙화

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
uv run pytest          # 전체 테스트
uv run pytest tests/unit -v  # 단위 테스트만
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
CORS_ORIGINS=["http://localhost:3000"]
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
| MinIO | 9000, 9001 | 파일 스토리지 (API, Console) |
| Neo4j | 7474, 7687 | 그래프 DB (Browser UI, Bolt) |
| LiveKit | 7880, 7881, 7882/udp | WebRTC SFU 서버 |
| LiveKit Egress | - (내부) | 서버 측 녹음 |
| STT Worker | - (내부) | 비동기 STT 처리 |
| Frontend | 3000 | nginx (정적 파일 + API 프록시) |
| Backend | 8000 (내부) | API 서버 |

### 환경변수

```bash
# docker/.env.example 참고
cp docker/.env.example docker/.env
# JWT_SECRET_KEY 등 수정
```

### 전체 실행 (Docker Compose)

```bash
# 전체 서비스 실행
make docker-up

# 로그 확인
make docker-logs

# 중지
make docker-down
```

---

## 프로덕션 배포

### 아키텍처

```
[Client] --> [Host nginx:443 SSL] --> [Docker nginx:3000] --> /api/* --> [backend:8000]
             (snsn.kr)                                    --> /*     --> static files
```

### 배포 방법

```bash
# 1. 환경변수 설정
cd docker
cp .env.example .env
# .env 수정:
#   JWT_SECRET_KEY=<openssl rand -hex 32>

# 2. shared-types 빌드 (최초 1회)
pnpm --filter @mit/shared-types build

# 3. Docker 실행
docker compose up -d --build

# 4. 마이그레이션 (최초 1회)
make db-upgrade
```

### Host nginx 설정 예시

```nginx
server {
    listen 80;
    server_name snsn.kr;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name snsn.kr;

    ssl_certificate /etc/letsencrypt/live/snsn.kr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/snsn.kr/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## API 목록

API 명세: `api-contract/openapi.yaml`

### 인증 API

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/auth/register | 회원가입 |
| POST | /api/v1/auth/login | 로그인 |
| POST | /api/v1/auth/refresh | 토큰 갱신 |
| POST | /api/v1/auth/logout | 로그아웃 |
| GET | /api/v1/auth/me | 현재 사용자 |

### 팀 API

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/teams | 팀 목록 |
| POST | /api/v1/teams | 팀 생성 |
| GET | /api/v1/teams/{id} | 팀 상세 |
| PATCH | /api/v1/teams/{id} | 팀 수정 |
| DELETE | /api/v1/teams/{id} | 팀 삭제 |

### 팀 멤버 API

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/teams/{id}/members | 멤버 목록 |
| POST | /api/v1/teams/{id}/members | 멤버 초대 |
| PATCH | /api/v1/teams/{id}/members/{userId} | 멤버 역할 변경 |
| DELETE | /api/v1/teams/{id}/members/{userId} | 멤버 제거 |

### 회의 API

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/meetings | 회의 목록 |
| POST | /api/v1/meetings | 회의 생성 |
| GET | /api/v1/meetings/{id} | 회의 상세 |
| PATCH | /api/v1/meetings/{id} | 회의 수정 |
| DELETE | /api/v1/meetings/{id} | 회의 삭제 |

### 회의 참여자 API

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/meetings/{id}/participants | 참여자 목록 |
| POST | /api/v1/meetings/{id}/participants | 참여자 추가 |
| PATCH | /api/v1/meetings/{id}/participants/{userId} | 참여자 역할 변경 |
| DELETE | /api/v1/meetings/{id}/participants/{userId} | 참여자 제거 |

### WebRTC API

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/meetings/{id}/room | 회의실 정보 |
| POST | /api/v1/meetings/{id}/start | 회의 시작 (host) |
| POST | /api/v1/meetings/{id}/end | 회의 종료 (host) |
| WS | /api/v1/meetings/{id}/ws?token=... | WebSocket 시그널링 |

### 녹음 API

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/meetings/{id}/recordings | 녹음 목록 조회 |
| POST | /api/v1/meetings/{id}/recordings/upload-url | Presigned URL 발급 |
| POST | /api/v1/meetings/{id}/recordings/{recordingId}/confirm | 업로드 완료 확인 |
| GET | /api/v1/meetings/{id}/recordings/{recordingId}/download | 녹음 다운로드 URL |

### Decision API

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/decisions/{id} | Decision 상세 조회 |
| POST | /api/v1/decisions/{id}/reviews | 리뷰 생성 (approve/reject) |
| GET | /api/v1/meetings/{id}/decisions | 회의의 Decision 목록 |

### 타입 생성

```bash
pnpm run generate:types
```

---

## 개발 워크플로우

### API 변경 시 (Contract First)

1. `api-contract/openapi.yaml` 또는 관련 스키마 파일 수정
2. `pnpm run generate:types` 실행
3. Backend 구현
4. Frontend 구현
5. 한 커밋에 모두 포함

### API Contract 패턴

**스키마 참조 규칙:**
```yaml
# paths -> schemas
$ref: '../schemas/team.yaml#/components/schemas/Team'

# schemas 내부 참조
$ref: '#/components/schemas/TeamRole'

# 공통 타입 (UUID, Timestamp)은 항상 common.yaml에서 참조
$ref: './common.yaml#/components/schemas/UUID'
```

**목록 응답 패턴:**
```yaml
SomeListResponse:
  properties:
    items: [...]        # 데이터 배열
    meta:               # 페이지네이션 메타
      $ref: './common.yaml#/components/schemas/PaginationMeta'
```

**스키마 확장 패턴 (allOf):**
```yaml
TeamWithMembers:
  allOf:
    - $ref: '#/components/schemas/Team'
    - type: object
      properties:
        members: [...]
```

### 코드 스타일

- TypeScript: camelCase (변수), PascalCase (타입/컴포넌트)
- Python: snake_case (변수/함수), PascalCase (클래스)
- API 경로: kebab-case (`/api/v1/meeting-reviews`)
- DB 테이블/컬럼: snake_case

---

## 트러블슈팅

### 브라우저 "오류 코드: 5" (페이지 크래시)

**원인**: localStorage에 손상된 데이터가 남아 있을 때 발생

**해결**:
```javascript
// 개발자 도구 > Console에서 실행
localStorage.clear()
// 이후 새로고침
```

### 배포 후 변경사항이 반영되지 않음

**원인**: 브라우저 캐시가 이전 버전 사용

**해결**:
1. 하드 리프레시: `Cmd+Shift+R` (Mac) / `Ctrl+Shift+R` (Windows)
2. 개발자 도구 > Network > "Disable cache" 체크

### shared-types 타입을 찾을 수 없음

**원인**: shared-types 패키지가 빌드되지 않음

**해결**:
```bash
pnpm --filter @mit/shared-types build
```

### DB 연결 오류

**원인**: 인프라가 실행되지 않았거나 환경변수가 잘못됨

**해결**:
```bash
# 인프라 상태 확인
docker ps

# 인프라 재시작
make infra-up

# 환경변수 확인
cat backend/.env | grep DATABASE_URL
```

### 마이그레이션 충돌

**원인**: 여러 브랜치에서 마이그레이션이 생성됨

**해결**:
```bash
cd backend

# 현재 상태 확인
uv run alembic history

# 헤드로 이동
uv run alembic upgrade head

# 충돌 시 수동으로 마이그레이션 파일 정리 필요
```

### 페이지 로드 안됨 (무한 로딩)

**원인**: useAuth hook에서 checkAuth가 무한 호출됨

**해결**:
1. 브라우저 콘솔에서 `[useAuth] Calling checkAuth...`가 반복되는지 확인
2. 최신 코드로 업데이트 (useRef로 중복 호출 방지됨)

### React error #185: Maximum update depth exceeded

**원인**: useWebRTC hook에서 store 전체 객체를 useCallback 의존성에 포함하여 무한 루프 발생

**해결**:
1. 브라우저 콘솔에서 에러 메시지 확인
2. 최신 코드로 업데이트 (개별 selector 사용으로 수정됨)

### 회의실 페이지(/meetings/{id}/room) 접근 시 에러 화면

**원인**: 회의 상태가 `ongoing`이 아니면 에러 메시지 표시

**해결**:
1. 회의 상세 페이지(`/meetings/{id}`)로 이동
2. Host가 "Start Meeting" 버튼 클릭하여 회의 시작
3. 회의 상태가 `ongoing`으로 변경되면 회의실 페이지 접근 가능

### 녹음 업로드 시 413 Request Entity Too Large

**원인**: nginx가 큰 파일 업로드를 차단 (기본 1MB 제한)

**해결**: Presigned URL 방식으로 MinIO에 직접 업로드 (nginx 우회)
- Frontend: `recordingService.uploadRecordingPresigned()` 사용
- 경로: Client -> nginx `/storage/*` -> MinIO (direct upload)

### 장시간 회의 중 401 Unauthorized

**원인**: access token 만료 (30분)

**해결**:
- useWebRTC에서 15분마다 자동 토큰 갱신
- `ensureValidToken()` 함수로 업로드 전 토큰 유효성 확인

### 새로고침 시 녹음 데이터 손실

**원인**: 메모리의 녹음 청크가 날아감

**해결**:
- IndexedDB에 10초마다 증분 저장
- beforeunload 시 localStorage에 백업 메타데이터 저장
- 다음 회의 입장 시 미완료 녹음 자동 업로드

---

## 라이선스

Private
