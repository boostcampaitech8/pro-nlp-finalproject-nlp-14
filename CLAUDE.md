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
│   ├── Dockerfile               # nginx 기반 프로덕션 이미지
│   ├── nginx.conf               # SPA 라우팅 + API 프록시
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
│   ├── docker-compose.yml       # infra + frontend + backend
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
- **발화자 구분 녹음**: 각 참여자의 오디오 트랙을 개별 파일로 저장

---

## 자주 사용하는 명령어

### Makefile (권장)
```bash
make help              # 전체 명령어 보기

# 개발 (로컬)
make install           # 의존성 설치
make dev               # FE + BE 로컬 실행
make dev-fe            # Frontend만 (http://localhost:3000)
make dev-be            # Backend만 (http://localhost:8000)

# Docker
make infra-up          # 인프라만 (DB, Redis, MinIO)
make docker-up         # 전체 (infra + frontend + backend)
make docker-down       # 전체 중지
make docker-logs       # 로그 보기
make docker-rebuild    # 이미지 재빌드

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

### 통합 배포 (권장)
```bash
# Docker Compose로 FE + BE 통합 배포
cd docker
cp .env.example .env
# .env에서 JWT_SECRET_KEY 변경
docker compose up -d --build
```

| 구성 | URL | 설명 |
|------|-----|------|
| 프로덕션 | `https://snsn.kr` | Host nginx SSL 종료 |
| 로컬 테스트 | `http://localhost:3000` | Docker nginx |

### 아키텍처
```
[Client] --> [Host nginx:443 SSL] --> [Docker nginx:3000] --> /api/* --> [backend:8000]
             (snsn.kr)                                    --> /*     --> static files
```

---

## 현재 진행 상황

### Phase 1: 미팅 시스템 (4주)

| 주차 | 기능 | 상태 | 비고 |
|------|------|------|------|
| Week 1 | 프로젝트 초기화 | 완료 | 모노레포, uv, Docker |
| Week 1 | 인증 (로그인/회원가입) | 완료 | JWT 기반 |
| Week 2 | 팀 CRUD | 완료 | API + UI |
| Week 2 | 회의 CRUD | 완료 | API + UI |
| Week 2 | 팀 멤버 관리 | 완료 | 초대/역할변경/제거 |
| Week 2 | 회의 참여자 관리 | 완료 | 추가/역할변경/제거 |
| Week 3 | WebRTC 시그널링 | 완료 | FastAPI WebSocket |
| Week 3 | 실시간 회의 (SFU) | 완료 | Mesh 시그널링 (SFU는 Week 4) |
| Week 4 | 서버 사이드 녹음 | 완료 | 하이브리드 아키텍처 (Mesh + 녹음) |
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
현재 목표: Phase 1 - Week 4 완료, 회의록 기본 기능 시작

다음 해야 할 작업:
1. [ ] 회의록 기본 기능 구현
2. [ ] 녹음 파일 STT 변환 (Whisper API 등)
3. [ ] 회의록 조회/수정 API
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

### 녹음
- 서버 사이드 녹음 시 **발화자 구분 필수**
- SFU에서 각 참여자의 오디오 트랙을 개별 파일로 저장
- 파일 경로 형식: `{meeting_id}/{user_id}_{timestamp}.webm`
- 녹음 메타데이터(시작/종료 시각, 발화자)를 DB에 저장
- MeetingRecording 모델: meeting_id, user_id, file_path, started_at, ended_at, duration_ms

---

## 트러블슈팅

### 브라우저 "오류 코드: 5" (렌더러 크래시)
- **원인**: localStorage에 손상된 데이터가 남아 있을 때 발생
- **해결**: 개발자 도구 > Console에서 `localStorage.clear()` 실행 후 새로고침

### 배포 후 변경사항 미반영 (304 Not Modified)
- **원인**: 브라우저가 이전 버전 캐시 사용
- **해결**:
  1. nginx.conf에서 index.html 캐시 방지 헤더 설정
  2. 하드 리프레시 (Cmd+Shift+R)

### shared-types 타입 인식 오류
- **원인**: shared-types 패키지가 빌드되지 않음
- **해결**: `pnpm --filter @mit/shared-types build` 실행

### 토큰 갱신 실패 시 페이지 먹통
- **원인**: api.ts에서 Promise reject 없이 redirect만 수행
- **해결**: `return Promise.reject(error)` 추가하여 에러 전파

### useAuth 무한 루프 (checkAuth 반복 호출)
- **원인**: useEffect 의존성 배열에 `store` 전체가 포함되어, `set()` 호출 시마다 재실행
- **해결**:
  1. `useRef`로 중복 호출 방지 (`isCheckingRef`)
  2. 의존성 배열을 `[store.isAuthenticated, store.user, store.checkAuth]`로 변경

### WebRTC 엔드포인트 422 에러
- **원인**: `AuthService.get_current_user`를 인스턴스 메서드인데 클래스 메서드처럼 사용
- **해결**: 올바른 FastAPI 의존성 주입 패턴 사용 (`get_auth_service` + `get_current_user` 함수)

### useWebRTC 무한 루프 (React error #185: Maximum update depth exceeded)
- **원인**: `useCallback` 의존성 배열에 `store` 전체 객체 포함 -> store 변경 시 콜백 재생성 -> useEffect 재실행 -> 무한 루프
- **해결**:
  1. 전체 store 대신 **개별 selector** 사용: `useMeetingRoomStore((s) => s.connectionState)`
  2. `hasCleanedUpRef`로 cleanup 중복 실행 방지
  3. `useEffect` cleanup에서 `useMeetingRoomStore.getState().reset()` 직접 호출 (빈 의존성 배열)

### 회의실 페이지 접근 시 에러 화면
- **원인**: 회의 상태가 `ongoing`이 아니면 에러 메시지 표시
- **해결**: 회의 상세 페이지에서 "Start Meeting" 버튼 클릭하여 회의 시작 필요

---

## 참고 문서

- `api-contract/openapi.yaml` - API 명세 (SSOT)
- `README.md` - 설치 및 실행 가이드

---

## 작업 로그

> 작업 완료 시 여기에 기록해주세요.

```
[2026-01-06] Phase 1 - Week 4 녹음 기능 완료
- 하이브리드 아키텍처: 기존 Mesh P2P 유지 + 녹음 전용 서버 연결
- Backend:
  - MinIO 스토리지 서비스 (storage.py)
  - MeetingRecording 모델 + Alembic 마이그레이션
  - aiortc 기반 RecordingSession, SFURoom, SFUService (sfu_service.py)
  - WebSocket 녹음 핸들러 (recording-offer, recording-ice, recording-answer)
  - 녹음 API 엔드포인트 (GET /meetings/{id}/recordings, GET .../download)
- Frontend:
  - 녹음 메시지 타입 추가 (webrtc.ts)
  - useWebRTC 훅에 startRecording, stopRecording 기능 추가
  - MeetingRoom에 녹음 버튼 UI 추가
- API Contract: recording.yaml 스키마/경로 추가
- 파일 경로: recordings/{meeting_id}/{user_id}_{timestamp}.webm

[2026-01-06] 버그 수정 (2차)
- useWebRTC 무한 루프 수정 (React error #185): 전체 store 대신 개별 selector 사용
- hasCleanedUpRef 추가로 cleanup 중복 실행 방지
- RemoteAudio 컴포넌트 추가 (원격 오디오 재생)

[2026-01-06] 버그 수정 (1차)
- useAuth 무한 루프 수정: useEffect 의존성 배열 개선 + useRef로 중복 호출 방지
- WebRTC 엔드포인트 422 에러 수정: FastAPI 의존성 주입 패턴 수정
- 콘솔 디버깅 로그 추가 (main.tsx, authStore.ts, api.ts, useAuth.ts, App.tsx)

[2026-01-06] Phase 1 - Week 3 완료
- WebRTC 시그널링 API 명세 작성: api-contract/schemas/webrtc.yaml, paths/webrtc.yaml
- Backend WebSocket 시그널링 구현: signaling_service.py, sfu_service.py, webrtc.py
- Frontend WebRTC 구현: signalingService.ts, webrtcService.ts, useWebRTC.ts
- 회의실 UI 구현: MeetingRoom.tsx, AudioControls.tsx, ParticipantList.tsx
- MeetingRoomPage 추가: /meetings/:meetingId/room 라우트
- MeetingDetailPage 수정: 회의 시작/참여/종료 버튼 추가
- 현재 Mesh 시그널링으로 동작, Week 4에서 실제 SFU + 녹음 구현 예정

[2026-01-06] Phase 1 - Week 2 완료
- Team API 구현: CRUD + 멤버 관리 (초대/역할변경/제거)
- Meeting API 구현: CRUD + 참여자 관리 (추가/역할변경/제거)
- Frontend UI 구현: 팀 목록/상세, 회의 목록/상세
- 멤버/참여자 관리 UI 구현: 초대 폼, 역할 수정, 제거 기능
- 버그 수정: 토큰 갱신 실패 시 Promise reject 처리 (api.ts)
- 버그 수정: index.html 캐시 방지 헤더 추가 (nginx.conf)
- 버그 수정: favicon 404 에러 수정 (inline SVG data URI)
- 트러블슈팅: 브라우저 오류 코드 5 해결 (localStorage.clear())

[2025-01-05] 통합 배포 구성 완료
- Frontend Dockerfile 추가 (nginx 기반 멀티스테이지 빌드)
- Frontend nginx.conf 추가 (SPA 라우팅 + /api 프록시)
- Docker Compose에 frontend 서비스 추가
- 아키텍처: Host nginx(443 SSL) -> Docker nginx(3000) -> backend(8000)
- 도메인: snsn.kr
- Makefile 업데이트 (frontend 명령어 추가)

[2024-12-31] Phase 1 - Week 1 완료
- 모노레포 구조 설정 완료 (pnpm workspace)
- Docker Compose 설정 완료 (PostgreSQL, Redis, MinIO, Backend)
- API Contract 작성 완료 (인증 API)
- shared-types 패키지 설정 완료
- Backend 초기화 완료 (FastAPI + SQLAlchemy + JWT + uv)
- Frontend 초기화 완료 (Vite + React + Tailwind + Zustand)
- Makefile 추가 (편의 명령어)
- 다음: Week 2 - 회의 CRUD 및 참여자 관리
```
