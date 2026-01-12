# Mit 모노레포 개발 가이드

## 1. 개요

### 1.1 목적
이 문서는 Claude Code를 활용하여 Mit 프로젝트를 개발할 때의 가이드라인입니다. FE와 BE를 모노레포로 통합하여 AI가 전체 맥락을 파악하고 일관된 코드를 생성할 수 있도록 합니다.

### 1.2 핵심 원칙
1. **Single Source of Truth**: API 명세(OpenAPI)가 유일한 진실의 원천
2. **원자적 변경**: API 변경 시 명세 + BE + FE를 한 번에 수정
3. **CLAUDE.md 중심**: AI가 세션 시작 시 프로젝트 맥락을 빠르게 파악
4. **타입 안전성**: 공유 타입으로 FE/BE 불일치 방지

---

## 2. 모노레포 구조

```
mit/
├── CLAUDE.md                    # AI 컨텍스트 (필수 읽기)
├── README.md                    # 프로젝트 소개
├── package.json                 # 루트 워크스페이스 설정
├── pnpm-workspace.yaml          # pnpm 워크스페이스
│
├── api-contract/                # API 명세 (SSOT)
│   ├── openapi.yaml             # OpenAPI 3.0 명세
│   ├── schemas/                 # 재사용 스키마
│   │   ├── user.yaml
│   │   ├── meeting.yaml
│   │   ├── review.yaml
│   │   └── knowledge.yaml
│   └── paths/                   # API 경로별 분리
│       ├── auth.yaml
│       ├── meetings.yaml
│       ├── notes.yaml
│       └── knowledge.yaml
│
├── packages/
│   └── shared-types/            # 공유 타입 패키지
│       ├── package.json
│       ├── tsconfig.json
│       └── src/
│           ├── index.ts
│           ├── user.ts
│           ├── meeting.ts
│           ├── review.ts
│           ├── knowledge.ts
│           └── api.ts           # OpenAPI에서 자동 생성
│
├── frontend/                    # React 앱
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── stores/
│   │   └── types/              # FE 전용 타입 (shared 외)
│   └── tests/
│
├── backend/                     # FastAPI 앱
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/            # Pydantic (OpenAPI에서 생성 가능)
│   │   ├── services/
│   │   └── webrtc/
│   └── tests/
│
├── docker/
│   ├── docker-compose.yml       # 로컬 개발 환경
│   ├── docker-compose.test.yml  # 테스트 환경
│   └── Dockerfile.*
│
└── scripts/
    ├── generate-types.sh        # OpenAPI → TypeScript 타입 생성
    ├── generate-schemas.sh      # OpenAPI → Pydantic 스키마 생성
    └── dev.sh                   # 개발 서버 실행
```

---

## 3. API Contract First 워크플로우

### 3.1 변경 순서 (필수)

```
┌─────────────────────────────────────────────────────────────────┐
│                    API 변경 워크플로우                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: api-contract/openapi.yaml 수정                         │
│  ────────────────────────────────────                           │
│  - 새 엔드포인트 추가 또는 기존 수정                             │
│  - Request/Response 스키마 정의                                 │
│  - 에러 케이스 정의                                             │
│                                                                 │
│  Step 2: 타입 생성                                              │
│  ────────────────────                                           │
│  $ pnpm run generate:types                                      │
│  - packages/shared-types/src/api.ts 자동 생성                   │
│  - backend/app/schemas/ 자동 생성 (선택)                        │
│                                                                 │
│  Step 3: Backend 구현                                           │
│  ─────────────────────                                          │
│  - 라우터 추가/수정                                             │
│  - 서비스 로직 구현                                             │
│  - 테스트 작성                                                  │
│                                                                 │
│  Step 4: Frontend 구현                                          │
│  ──────────────────────                                         │
│  - API 호출 서비스 추가                                         │
│  - 컴포넌트/페이지 구현                                         │
│  - 테스트 작성                                                  │
│                                                                 │
│  Step 5: 통합 검증                                              │
│  ─────────────────                                              │
│  $ pnpm run typecheck     # 타입 체크                           │
│  $ pnpm run test          # 전체 테스트                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 OpenAPI 명세 작성 규칙

```yaml
# api-contract/openapi.yaml
openapi: 3.0.0
info:
  title: Mit API
  version: 1.0.0

servers:
  - url: http://localhost:8000/api/v1
    description: 로컬 개발

paths:
  /meetings:
    $ref: './paths/meetings.yaml#/meetings'
  /meetings/{id}:
    $ref: './paths/meetings.yaml#/meetings-id'

components:
  schemas:
    $ref: './schemas/_index.yaml'
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

```yaml
# api-contract/paths/meetings.yaml
meetings:
  get:
    operationId: listMeetings
    summary: 회의 목록 조회
    tags: [Meeting]
    security:
      - BearerAuth: []
    parameters:
      - name: page
        in: query
        schema:
          type: integer
          default: 1
      - name: limit
        in: query
        schema:
          type: integer
          default: 20
      - name: status
        in: query
        schema:
          $ref: '../schemas/meeting.yaml#/MeetingStatus'
    responses:
      '200':
        description: 성공
        content:
          application/json:
            schema:
              $ref: '../schemas/meeting.yaml#/MeetingsListResponse'
      '401':
        $ref: '../schemas/_errors.yaml#/Unauthorized'

  post:
    operationId: createMeeting
    summary: 회의 생성
    tags: [Meeting]
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '../schemas/meeting.yaml#/CreateMeetingRequest'
    responses:
      '201':
        description: 생성 완료
        content:
          application/json:
            schema:
              $ref: '../schemas/meeting.yaml#/Meeting'
      '400':
        $ref: '../schemas/_errors.yaml#/ValidationError'
      '401':
        $ref: '../schemas/_errors.yaml#/Unauthorized'
```

```yaml
# api-contract/schemas/meeting.yaml
MeetingStatus:
  type: string
  enum: [scheduled, in_progress, completed, cancelled]

Meeting:
  type: object
  required: [id, title, status, creator, created_at]
  properties:
    id:
      type: string
      format: uuid
    title:
      type: string
      maxLength: 200
    description:
      type: string
      nullable: true
    status:
      $ref: '#/MeetingStatus'
    scheduled_at:
      type: string
      format: date-time
      nullable: true
    creator:
      $ref: './user.yaml#/UserSummary'
    participants_count:
      type: integer
    created_at:
      type: string
      format: date-time

CreateMeetingRequest:
  type: object
  required: [title]
  properties:
    title:
      type: string
      maxLength: 200
    description:
      type: string
    scheduled_at:
      type: string
      format: date-time
    participant_ids:
      type: array
      items:
        type: string
        format: uuid

MeetingsListResponse:
  type: object
  required: [meetings, total, page, limit]
  properties:
    meetings:
      type: array
      items:
        $ref: '#/Meeting'
    total:
      type: integer
    page:
      type: integer
    limit:
      type: integer
```

### 3.3 타입 생성 스크립트

```bash
#!/bin/bash
# scripts/generate-types.sh

echo "Generating TypeScript types from OpenAPI..."

# OpenAPI → TypeScript
npx openapi-typescript ./api-contract/openapi.yaml \
  -o ./packages/shared-types/src/api.generated.ts

echo "TypeScript types generated!"

# (선택) OpenAPI → Pydantic
# pip install datamodel-code-generator
# datamodel-codegen \
#   --input ./api-contract/openapi.yaml \
#   --output ./backend/app/schemas/generated.py

echo "Done!"
```

---

## 4. Claude Code 활용 패턴

### 4.1 세션 시작 시

Claude Code는 세션 시작 시 `CLAUDE.md`를 읽습니다. 이 파일에 다음을 포함:

1. 프로젝트 구조 개요
2. 현재 진행 상황 (Phase, 완료/진행중/대기)
3. 핵심 규칙 (API Contract First 등)
4. 자주 사용하는 명령어

### 4.2 효과적인 요청 패턴

**좋은 요청 (원자적, 구체적):**
```
"회의 생성 API를 구현해줘.
1. api-contract/paths/meetings.yaml에 POST /meetings 추가
2. backend/app/api/v1/meetings.py에 라우터 구현
3. frontend/src/services/meeting.service.ts에 API 호출 함수 추가
4. frontend/src/pages/MeetingCreatePage.tsx 구현"
```

**나쁜 요청 (모호함):**
```
"회의 기능 만들어줘"
```

### 4.3 점진적 개발 패턴

```
Phase 1 - Week 1 요청 예시:

1. "api-contract에 인증 관련 API 명세를 작성해줘 (login, register, me)"

2. "백엔드에 인증 API를 구현해줘. JWT 기반으로."

3. "프론트엔드에 로그인/회원가입 페이지를 만들어줘."

4. "인증 흐름 E2E 테스트를 작성해줘."
```

### 4.4 컨텍스트 유지 팁

긴 개발 세션에서 Claude가 맥락을 잃지 않도록:

1. **주기적 상태 업데이트**: 
   ```
   "현재까지 완료된 것: 인증 API, 회의 CRUD
    다음 작업: WebRTC 시그널링"
   ```

2. **CLAUDE.md 업데이트 요청**:
   ```
   "지금까지 작업한 내용을 CLAUDE.md의 진행 상황에 반영해줘"
   ```

3. **특정 파일 참조**:
   ```
   "api-contract/openapi.yaml을 보고 아직 구현 안 된 API가 뭔지 알려줘"
   ```

---

## 5. 개발 환경 설정

### 5.1 필수 도구

```bash
# Node.js (pnpm 사용)
npm install -g pnpm

# Python
python3.11 -m venv .venv
source .venv/bin/activate

# Docker (DB, Redis 등)
docker-compose up -d
```

### 5.2 워크스페이스 설정

```yaml
# pnpm-workspace.yaml
packages:
  - 'packages/*'
  - 'frontend'
```

```json
// package.json (루트)
{
  "name": "mit",
  "private": true,
  "scripts": {
    "dev": "./scripts/dev.sh",
    "dev:fe": "pnpm --filter frontend dev",
    "dev:be": "cd backend && uvicorn app.main:app --reload",
    "generate:types": "./scripts/generate-types.sh",
    "typecheck": "pnpm --filter frontend typecheck && pnpm --filter shared-types typecheck",
    "test": "pnpm --filter frontend test && cd backend && pytest",
    "lint": "pnpm --filter frontend lint && cd backend && ruff check ."
  },
  "devDependencies": {
    "openapi-typescript": "^6.7.0"
  }
}
```

### 5.3 Docker Compose

```yaml
# docker/docker-compose.yml
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: mit
      POSTGRES_PASSWORD: mit
      POSTGRES_DB: mit
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

---

## 6. 브랜치 전략

모노레포이므로 단순한 브랜치 전략 사용:

```
main                    # 운영 배포
│
├── develop             # 개발 통합
│   │
│   ├── feature/*       # 기능 브랜치
│   │   ├── feature/auth
│   │   ├── feature/meeting-crud
│   │   ├── feature/webrtc
│   │   └── feature/review-system
│   │
│   └── fix/*           # 버그 수정
│
└── release/*           # 릴리스 브랜치
```

**커밋 메시지 규칙:**
```
feat(fe): 로그인 페이지 구현
feat(be): 회의 생성 API 구현
feat(contract): 회의 API 명세 추가
fix(fe): 회의 목록 페이지네이션 버그 수정
docs: CLAUDE.md 진행 상황 업데이트
```

---

## 7. 테스트 전략

### 7.1 레이어별 테스트

| 레이어 | 테스트 도구 | 위치 |
|--------|-------------|------|
| API Contract | Spectral (린트) | api-contract/ |
| Backend Unit | pytest | backend/tests/unit/ |
| Backend Integration | pytest + httpx | backend/tests/integration/ |
| Frontend Unit | Vitest | frontend/tests/unit/ |
| Frontend Component | Testing Library | frontend/tests/components/ |
| E2E | Playwright | e2e/ |

### 7.2 Contract 테스트

```typescript
// frontend/tests/contract/meetings.test.ts
import { describe, it, expect } from 'vitest';
import { api } from '@/services/api';

describe('Meetings API Contract', () => {
  it('GET /meetings returns correct shape', async () => {
    const response = await api.get('/meetings');
    
    expect(response.data).toHaveProperty('meetings');
    expect(response.data).toHaveProperty('total');
    expect(response.data).toHaveProperty('page');
    expect(Array.isArray(response.data.meetings)).toBe(true);
  });
});
```

---

## 8. 체크리스트

### 8.1 새 기능 개발 전
- [ ] api-contract/openapi.yaml에 명세가 있는가?
- [ ] `pnpm run generate:types` 실행했는가?
- [ ] CLAUDE.md 진행 상황이 최신인가?

### 8.2 PR 전
- [ ] `pnpm run typecheck` 통과하는가?
- [ ] `pnpm run test` 통과하는가?
- [ ] `pnpm run lint` 통과하는가?
- [ ] API 변경 시 명세 + BE + FE 모두 수정했는가?

### 8.3 Phase 완료 시
- [ ] 모든 API 엔드포인트가 구현되었는가?
- [ ] E2E 테스트가 통과하는가?
- [ ] CLAUDE.md 진행 상황 업데이트했는가?
