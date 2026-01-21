# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## AI Guidance

* DO NOT use Emoji. 코드 주석은 한글로 작성.
* ALWAYS read and understand relevant files before proposing code edits.
* Do what has been asked; nothing more, nothing less.
* ALWAYS prefer editing an existing file to creating a new one.
* NEVER proactively create documentation files (*.md) or README files unless explicitly requested.
* When asked to commit changes, exclude CLAUDE.md and CLAUDE-*.md files from commits.
* For code searches and analysis, use code-searcher subagent where appropriate.
* For maximum efficiency, invoke multiple independent tools simultaneously rather than sequentially.
* After completing a task that involves tool use, provide a quick summary of what you've done.
* When you update or modify core context files, also update markdown documentation and memory bank.

<investigate_before_answering>
Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering. Make sure to investigate and read relevant files BEFORE answering questions about the codebase. Never make any claims about code before investigating unless you are certain of the correct answer - give grounded and hallucination-free answers.
</investigate_before_answering>

<do_not_act_before_instructions>
Do not jump into implementation or change files unless clearly instructed to make changes. When the user's intent is ambiguous, default to providing information, doing research, and providing recommendations rather than taking action. Only proceed with edits, modifications, or implementations when the user explicitly requests them.
</do_not_act_before_instructions>

## Memory Bank System

This project uses a structured memory bank system with specialized context files. Always check these files for relevant information before starting work:

### Core Context Files

* **CLAUDE-activeContext.md** - Current session state, goals, and progress (if exists)
* **CLAUDE-patterns.md** - Established code patterns and conventions (if exists)
* **CLAUDE-decisions.md** - Architecture decisions and rationale (if exists)
* **CLAUDE-troubleshooting.md** - Common issues and proven solutions (if exists)
* **CLAUDE-config-variables.md** - Configuration variables reference (if exists)
* **CLAUDE-temp.md** - Temporary scratch pad (only read when referenced)

**Important:** Always reference the active context file first to understand what's currently being worked on and maintain session continuity.

### Memory Bank System Backups

When asked to backup Memory Bank System files, copy the core context files above and .claude settings directory to the specified backup directory. If files already exist in the backup directory, overwrite them.

## Fast CLI Tools

### BANNED - Never Use These Slow Tools

* `tree` - NOT INSTALLED, use `fd` instead
* `find` - use `fd` or `rg --files`
* `grep` or `grep -r` - use `rg` instead
* `ls -R` - use `rg --files` or `fd`
* `cat file | grep` - use `rg pattern file`

### Use These Instead

```bash
# ripgrep (rg) - content search
rg "search_term"                # Search in all files
rg -i "case_insensitive"        # Case-insensitive
rg "pattern" -t py              # Only Python files
rg "pattern" -g "*.md"          # Only Markdown
rg -l "pattern"                 # Filenames with matches
rg -c "pattern"                 # Count matches per file
rg -n "pattern"                 # Show line numbers
rg -A 3 -B 3 "error"            # Context lines

# ripgrep (rg) - file listing
rg --files                      # List files (respects .gitignore)
rg --files | rg "pattern"       # Find files by name
rg --files -t md                # Only Markdown files

# fd - file finding
fd . -t f                       # All files (fastest)
fd . -t d                       # All directories
fd -e js                        # All .js files
fd "filename"                   # Find by name pattern

# jq - JSON processing
jq . data.json                  # Pretty-print
jq -r .name file.json           # Extract field
```

### Decision Tree

```
"list/show/summarize/explore files" → fd . -t f OR rg --files
"search/grep/find text content"     → rg "pattern" (NOT grep!)
"find file/directory by name"       → fd "name" (NOT find!)
"directory structure/tree"          → fd . -t d + fd . -t f (NOT tree!)
"current directory only"            → ls -la
```

## Project Overview

**Mit**는 "Git이 코드의 진실을 관리하듯, 조직 회의의 진실을 관리하는" 협업 기반 조직 지식 시스템입니다.

핵심 컨셉:
- 회의록을 PR Review 스타일로 팀원들이 검토/합의
- 합의된 내용만 조직의 Ground Truth(GT)로 확정
- 회의마다 GT가 축적되어 조직 지식 DB 성장

## Commands

### Development (Local)
```bash
make install           # 의존성 설치
make dev               # FE + BE 로컬 실행
make dev-fe            # Frontend (http://localhost:3000)
make dev-be            # Backend (http://localhost:8000)
```

### Docker
```bash
make infra-up          # 인프라만 (DB, Redis, MinIO)
make docker-up         # 전체 (infra + frontend + backend)
make docker-down       # 전체 중지
make docker-logs       # 로그 보기
make docker-rebuild    # 이미지 재빌드
```

### DB Migration
```bash
make db-migrate m="설명"  # 마이그레이션 생성
make db-upgrade           # 마이그레이션 적용
make db-downgrade         # 롤백
```

### Type Generation
```bash
pnpm run generate:types   # OpenAPI -> TypeScript 타입 생성
```

### Backend (uv)
```bash
cd backend
uv sync                # 의존성 설치
uv add <package>       # 패키지 추가
uv run pytest          # 테스트 실행
```

### Backup
```bash
make backup                              # PostgreSQL, MinIO, Redis 전체 백업
make backup-list                         # 백업 목록 조회
make backup-restore name=YYYYMMDD_HHMMSS # 특정 백업에서 복원
```

백업 저장 위치: `backup/YYYYMMDD_HHMMSS/` (postgres/, minio/, redis/)

## Architecture

```
mit/
├── api-contract/                # API 명세 (SSOT) - OpenAPI 3.0
├── packages/shared-types/       # FE/BE 공유 타입 (자동 생성)
├── frontend/
│   └── src/
│       ├── app/                 # Spotlight 메인 서비스 (3-column 레이아웃)
│       │   ├── components/      # spotlight/, sidebar/, meeting/, preview/, ui/
│       │   ├── constants/       # 상수 (HISTORY_LIMIT, STATUS_COLORS, API_DELAYS)
│       │   ├── hooks/           # useCommand.ts
│       │   ├── layouts/         # MainLayout.tsx
│       │   ├── pages/           # MainPage.tsx
│       │   ├── services/        # agentService.ts
│       │   ├── stores/          # commandStore, meetingModalStore, previewStore
│       │   ├── types/           # command.ts
│       │   └── utils/           # dateUtils (formatRelativeTime, formatDuration)
│       ├── components/          # 회의실 컴포넌트 (meeting/, team/, ui/)
│       ├── dashboard/           # 대시보드 페이지
│       ├── hooks/               # LiveKit, VAD, 오디오 디바이스 훅
│       ├── services/            # API 서비스
│       └── stores/              # authStore, teamStore, meetingRoomStore
├── backend/                     # FastAPI + Python 3.11 + SQLAlchemy 2.0 + uv
│   └── workers/                 # ARQ Worker (STT 비동기 처리)
└── docker/                      # Docker Compose (PostgreSQL, Redis, MinIO, stt-worker)
```

### WebRTC Architecture (LiveKit SFU)
- **LiveKit SFU**: 중앙 서버 기반 미디어 라우팅 (Mesh P2P 대체)
- **TURN TLS**: NAT/방화벽 환경 WebRTC 연결용 (turn.mit-hub.com:5349, Let's Encrypt 인증서)
- **서버 녹음**: LiveKit Egress -> MinIO 직접 저장 (클라이언트 녹음 제거)
- **클라이언트 VAD**: @ricky0123/vad-web -> DataPacket으로 발화 이벤트 서버 전송
- **오디오 컨트롤**: 마이크 게인 조절, 디바이스 선택 (Web Audio GainNode)
- **설정 캐싱**: localStorage에 오디오 설정, 참여자별 볼륨 저장 (회의 간 유지)
- **실시간 STT 준비**: VAD 이벤트 서버 수집 (추후 STT 트리거용)

### Legacy WebRTC (Removed)
- **Mesh P2P**: 레거시 코드 삭제됨 (useWebRTC.ts, useSignaling.ts, usePeerConnections.ts)

### Deployment Architecture
```
[Client] --> [Host nginx:443 SSL] --> [Docker nginx:3000] --> /api/*     --> [backend:8000]
             (snsn.kr)                                    --> /livekit/* --> [livekit:7880] (WebSocket)
                                                          --> /storage/* --> [minio:9000]
                                                          --> /*         --> static files
```

## Key Components

### Frontend - Spotlight Service (src/app/)
| 파일 | 역할 |
|------|------|
| `app/layouts/MainLayout.tsx` | 3-column 레이아웃 (280px-flex-400px) |
| `app/pages/MainPage.tsx` | 메인 서비스 페이지 |
| `app/components/spotlight/SpotlightInput.tsx` | 명령어 입력창 (자동완성) |
| `app/components/sidebar/LeftSidebar.tsx` | 좌측 사이드바 (네비게이션, 세션) |
| `app/components/sidebar/Navigation.tsx` | 팀 목록, 메뉴 |
| `app/components/sidebar/CurrentSession.tsx` | 현재 회의 상태 |
| `app/components/meeting/MeetingModal.tsx` | 회의 생성 모달 |
| `app/hooks/useCommand.ts` | 명령어 실행 훅 |
| `app/services/agentService.ts` | 명령어 매칭/처리 |
| `app/stores/commandStore.ts` | 명령어 입력/히스토리 상태 |
| `app/stores/meetingModalStore.ts` | 회의 모달 상태 |
| `app/stores/previewStore.ts` | 미리보기 패널 상태 |
| `app/constants/index.ts` | 상수 (HISTORY_LIMIT, STATUS_COLORS, API_DELAYS) |
| `app/utils/dateUtils.ts` | 날짜 유틸 (formatRelativeTime, formatDuration) |

### Frontend - Meeting Room (src/)
| 파일 | 역할 |
|------|------|
| `hooks/useLiveKit.ts` | LiveKit SFU 연결, DataPacket 통신, 서버 녹음 (핵심 훅) |
| `hooks/useVAD.ts` | 클라이언트 VAD (Silero VAD, @ricky0123/vad-web) |
| `hooks/useAudioDevices.ts` | 오디오 디바이스 선택 |
| `stores/meetingRoomStore.ts` | 회의실 상태 (스트림, 참여자, 연결, localStorage 설정 캐싱) |
| `utils/audioSettingsStorage.ts` | localStorage 오디오 설정 캐싱 (마이크 게인, 디바이스, 볼륨) |
| `services/transcriptService.ts` | STT 시작/상태조회/결과조회 |
| `services/chatService.ts` | 채팅 히스토리 조회 |
| `components/meeting/MeetingRoom.tsx` | 회의실 메인 컴포넌트 |
| `components/meeting/RecordingList.tsx` | 녹음 목록 (Audio/Transcript 다운로드) |
| `components/meeting/RemoteAudio.tsx` | 원격 오디오 재생 (Web Audio API GainNode) |
| `components/meeting/TranscriptSection.tsx` | 트랜스크립트 표시 (실제 시각 timestamp 포함) |
| `components/meeting/ChatPanel.tsx` | 채팅 UI (Markdown, 연속 메시지 그룹화) |
| `components/ui/MarkdownRenderer.tsx` | Markdown 렌더링 (react-markdown) |

### Backend
| 파일 | 역할 |
|------|------|
| `api/dependencies.py` | 공유 의존성 (인증, 회의 검증) - DRY 원칙 |
| `core/constants.py` | 애플리케이션 상수 (파일 크기, URL 만료 시간) |
| `services/livekit_service.py` | LiveKit 토큰 생성 및 Egress 녹음 관리 |
| `services/chat_service.py` | 채팅 메시지 CRUD |
| `api/v1/endpoints/webrtc.py` | LiveKit 토큰 발급 및 녹음 API |
| `api/v1/endpoints/livekit_webhooks.py` | LiveKit 이벤트 웹훅 (녹음 완료, 참여자 변경) |
| `api/v1/endpoints/recordings.py` | 녹음 다운로드 API |
| `api/v1/endpoints/transcripts.py` | STT 시작/상태/조회 API |
| `api/v1/endpoints/chat.py` | 채팅 히스토리 API |
| `core/storage.py` | MinIO 스토리지 서비스 |
| `services/stt_service.py` | STT 변환 로직 |
| `services/transcript_service.py` | 회의록 병합/관리 (wall-clock timestamp 기반 정렬) |
| `services/stt/base.py` | STT Provider 추상 클래스 |
| `services/stt/openai_provider.py` | OpenAI Whisper 구현체 |
| `workers/arq_worker.py` | ARQ 비동기 작업 Worker |
| `models/chat.py` | ChatMessage 모델 |

### Backend Design Patterns
- **Service Layer**: `LiveKitService` - 토큰 생성, Egress 녹음 관리
- **Webhook Pattern**: `livekit_webhooks.py` - LiveKit 이벤트 수신 및 처리
- **Shared Dependencies**: `api/dependencies.py` - 중복 코드 180+ lines 제거
- **Provider Pattern**: `stt/` - STT Provider 추상화 (OpenAI/Local/Self-hosted 확장)
- **Async Worker**: `workers/arq_worker.py` - ARQ 기반 비동기 STT 처리

## Critical Rules

### 1. API Contract First
API 변경 시 반드시 이 순서로 작업:
```
1. api-contract/openapi.yaml 수정
2. pnpm run generate:types 실행
3. backend 구현
4. frontend 구현
```
API 변경은 명세 + BE + FE를 **한 커밋 또는 한 PR**에서 함께 수정.

### 2. Naming Conventions
- API 경로: kebab-case (`/api/v1/meeting-reviews`)
- DB 테이블/컬럼: snake_case (`meeting_reviews`, `created_at`)
- TypeScript: camelCase (변수), PascalCase (타입/컴포넌트)
- Python: snake_case (변수/함수), PascalCase (클래스)

### 3. API Design
- 모든 목록 API는 페이지네이션 필수 (`page`, `limit`, `total`)
- 에러 응답 형식 통일: `{ error: string, message: string, details?: object }`
- UUID 사용 (auto-increment ID 사용 금지)
