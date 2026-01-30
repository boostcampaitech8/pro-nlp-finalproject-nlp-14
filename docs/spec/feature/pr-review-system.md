# PR Review 시스템

> 목적: MitHub의 GitHub-스타일 PR Review 시스템을 설명한다.
> 대상: 기획/개발 전원.
> 범위: Decision 리뷰 UI/UX, 승인 플로우, 상태 관리.
> 비범위: Agent 워크플로우 세부 구현, Neo4j 쿼리 최적화.

---

## 1. 개요

MitHub의 PR Review 시스템은 회의에서 도출된 Decision을 팀원들이 검토하고 합의하는 Git PR 스타일의 협업 시스템입니다.

### 1.1 핵심 개념

```
┌─────────────────────────────────────────────────────────────────┐
│                    PR Review 핵심 개념                            │
└─────────────────────────────────────────────────────────────────┘

Meeting
   │
   └─▶ Minutes (회의록 초안)
          │
          └─▶ Agenda (안건)
                 │
                 └─▶ Decision (의사결정)
                        │
                        ├─▶ Approve (승인)  ───▶ latest (GT 반영)
                        │
                        └─▶ Reject (거부)   ───▶ rejected
```

### 1.2 Ground Truth (GT) 개념

- **GT (Ground Truth)**: 팀이 합의한 공식 의사결정
- Decision이 `latest` 상태가 되면 GT로 확정
- GT는 조직 지식 DB의 기준점

---

## 2. Decision 상태 관리

### 2.1 상태 정의

| 상태 | 설명 | UI 표시 |
|------|------|---------|
| `draft` | 리뷰 대기 중 | 노란색 배지 |
| `latest` | 현재 유효한 GT | 파란색 배지 |
| `outdated` | 새 Decision으로 대체됨 | 회색 배지 |
| `approved` | 승인됨 (부분) | 초록색 배지 |
| `rejected` | 거부됨 | 빨간색 배지 |

### 2.2 상태 전이 다이어그램

```
              ┌──────────┐
              │  draft   │ (초기 상태)
              └────┬─────┘
                   │
         ┌─────────┼─────────┐
         │         │         │
         ▼         ▼         ▼
   ┌──────────┐         ┌──────────┐
   │ approved │         │ rejected │
   │ (부분)   │         │ (최종)   │
   └────┬─────┘         └──────────┘
        │
        │ 전원 승인
        ▼
   ┌──────────┐
   │  latest  │ ───────▶ GT 반영
   └────┬─────┘
        │
        │ 새 Decision 승인
        ▼
   ┌──────────┐
   │ outdated │
   └──────────┘
```

### 2.3 전원 승인 규칙

```
회의 참석자 전원이 Approve해야 Decision이 `latest`로 승격

예시: 3명 참석자
- 1명 Approve → draft (진행 중)
- 2명 Approve → draft (진행 중)
- 3명 Approve → latest (GT 확정)
```

---

## 3. UI 컴포넌트

### 3.1 컴포넌트 계층

```
PRReviewPage
├── MinutesHeader (회의 정보)
│   ├── 회의 제목/설명
│   ├── 회의 일시
│   └── 참여자 목록
├── PRStatusBadge (PR 상태)
│   ├── open/closed 상태
│   └── 승인 진행률
└── DecisionList (Decision 그룹)
    └── DecisionCard[] (개별 Decision)
        ├── 상태 배지
        ├── Decision 내용
        ├── 승인 진행률
        ├── 참여자별 상태 아이콘
        └── Approve/Reject 버튼
```

### 3.2 DecisionCard UI

```
┌────────────────────────────────────────────────────────────┐
│ [draft] 신규 API 엔드포인트 추가 결정                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ 내용: 사용자 프로필 API를 /users/{id}/profile로 변경           │
│                                                            │
│ 맥락: 기존 /profile 엔드포인트가 인증 흐름과 충돌...           │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ 승인: 2/3                                                  │
│ ✅ 김개발  ✅ 이기획  ⏳ 박디자인                              │
├────────────────────────────────────────────────────────────┤
│                              [Reject]  [Approve]           │
└────────────────────────────────────────────────────────────┘
```

### 3.3 참여자 상태 아이콘

| 아이콘 | 의미 |
|--------|------|
| ✅ (체크) | 승인함 |
| ❌ (X) | 거부함 |
| ⏳ (시계) | 대기 중 |

---

## 4. API 엔드포인트

### 4.1 Decision 목록 조회

```
GET /api/v1/meetings/{meeting_id}/decisions

Response:
{
  "decisions": [
    {
      "id": "decision-uuid",
      "content": "결정 내용",
      "context": "결정 맥락",
      "status": "draft",
      "agenda_id": "agenda-uuid",
      "agenda_topic": "안건 주제",
      "created_at": "2026-01-29T10:00:00Z",
      "approvers": ["user-1", "user-2"],
      "rejectors": []
    }
  ],
  "total": 5
}
```

### 4.2 Decision 승인/거부

```
POST /api/v1/decisions/{decision_id}/reviews

Request:
{
  "action": "approve" | "reject"
}

Response:
{
  "decision_id": "decision-uuid",
  "action": "approve",
  "user_id": "user-uuid",
  "is_merged": true,
  "message": "Decision이 승인되어 GT로 반영되었습니다."
}
```

### 4.3 단일 Decision 조회

```
GET /api/v1/decisions/{decision_id}

Response:
{
  "id": "decision-uuid",
  "content": "결정 내용",
  "context": "결정 맥락",
  "status": "latest",
  "agenda_id": "agenda-uuid",
  "meeting_id": "meeting-uuid",
  "meeting_title": "회의 제목",
  "approvers": ["user-1", "user-2", "user-3"],
  "rejectors": [],
  "created_at": "2026-01-29T10:00:00Z",
  "approved_at": "2026-01-29T11:00:00Z"
}
```

---

## 5. 상태 관리 (Zustand)

### 5.1 prReviewStore 구조

```typescript
interface PRReviewState {
  // 상태
  meeting: Meeting | null;
  decisions: Decision[];
  agendas: PRAgenda[];
  prStatus: PRStatus;
  loading: boolean;
  error: string | null;

  // 액션
  fetchMeetingReview: (meetingId: string) => Promise<void>;
  approveDecision: (decisionId: string) => Promise<void>;
  rejectDecision: (decisionId: string) => Promise<void>;
  refetchDecision: (decisionId: string) => Promise<void>;
}
```

### 5.2 Optimistic Update 패턴

```typescript
async approveDecision(decisionId: string) {
  // 1. 로딩 상태 설정
  set({ loading: true });

  try {
    // 2. API 호출
    const result = await prReviewService.approveDecision(decisionId);

    // 3. 최신 Decision 데이터 조회
    const updatedDecision = await prReviewService.getDecision(decisionId);

    // 4. 로컬 상태 업데이트
    set((state) => ({
      decisions: state.decisions.map(d =>
        d.id === decisionId ? updatedDecision : d
      ),
      loading: false
    }));

    // 5. Agenda 그룹 및 PR 상태 재계산
    recalculateAgendas();
    recalculatePRStatus();

  } catch (error) {
    set({ error: error.message, loading: false });
  }
}
```

---

## 6. Neo4j 그래프 구조

### 6.1 노드 및 관계

```cypher
// 노드
(:Meeting {id, title, status, created_at})
(:Agenda {id, topic, description})
(:Decision {id, content, context, status, created_at, approved_at})
(:User {id, name, email})

// 관계
(Meeting)-[:CONTAINS]->(Agenda)
(Agenda)-[:HAS_DECISION]->(Decision)
(User)-[:PARTICIPATED_IN]->(Meeting)
(User)-[:APPROVED_BY]->(Decision)
(User)-[:REJECTED_BY]->(Decision)
(Decision:latest)-[:SUPERSEDES]->(Decision:outdated)
```

### 6.2 전원 승인 + 자동 Merge 쿼리

```cypher
// 승인 + 전원 확인 + 상태 변경 (원자적 트랜잭션)
MATCH (d:Decision {id: $decision_id})<-[:HAS_DECISION]-(a:Agenda)<-[:CONTAINS]-(m:Meeting)
MATCH (u:User {id: $user_id})

// 승인 관계 생성
MERGE (u)-[:APPROVED_BY]->(d)

// 참여자 수 vs 승인자 수 확인
WITH d, m
MATCH (participant:User)-[:PARTICIPATED_IN]->(m)
WITH d, collect(participant) as participants

MATCH (approver:User)-[:APPROVED_BY]->(d)
WITH d, participants, collect(approver) as approvers

// 전원 승인 시 상태 변경
WHERE size(approvers) = size(participants)
SET d.status = 'latest', d.approved_at = datetime()

// 기존 latest Decision을 outdated로 변경
WITH d
MATCH (old:Decision {status: 'latest'})<-[:HAS_DECISION]-(a:Agenda)-[:HAS_DECISION]->(d)
WHERE old.id <> d.id
SET old.status = 'outdated'
MERGE (d)-[:SUPERSEDES]->(old)

RETURN d
```

---

## 7. 후처리: Action Item 추출

### 7.1 Merge 후 자동 트리거

```python
# ReviewService.create_review()
async def create_review(self, decision_id: str, user_id: str, action: str):
    result = await self.kg_repo.approve_and_merge_if_complete(decision_id, user_id)

    if result.is_merged:
        # ARQ Worker로 mit-action 작업 큐잉
        await self.arq_pool.enqueue_job(
            "mit_action_task",
            decision_id=decision_id
        )

    return result
```

### 7.2 mit-action 워크플로우

```
Decision Merge 완료
        │
        ▼ (ARQ 비동기)
┌─────────────────────────────────────┐
│ mit_action_task                     │
│ 1. Decision 데이터 조회              │
│ 2. LangGraph mit_action 실행        │
│ 3. Action Item 추출                 │
│ 4. Neo4j 저장                       │
└─────────────────────────────────────┘
        │
        ▼
(Decision)-[:HAS_ACTION]->(ActionItem)
```

---

## 8. PR 상태 계산

### 8.1 클라이언트 사이드 계산

```typescript
function calculatePRStatus(decisions: Decision[]): PRStatus {
  const pending = decisions.filter(d => d.status === 'draft');
  const approved = decisions.filter(d => d.status === 'latest' || d.status === 'approved');
  const rejected = decisions.filter(d => d.status === 'rejected');

  return {
    status: pending.length === 0 ? 'closed' : 'open',
    totalDecisions: decisions.length,
    approvedCount: approved.length,
    rejectedCount: rejected.length,
    pendingCount: pending.length
  };
}
```

### 8.2 PR 상태 정의

| 상태 | 조건 | 설명 |
|------|------|------|
| `open` | pending Decision 존재 | 리뷰 진행 중 |
| `closed` | 모든 Decision 처리 완료 | 리뷰 완료 |

---

## 9. 파일 구조

### 9.1 Frontend

```
frontend/src/
├── dashboard/
│   ├── pages/
│   │   └── PRReviewPage.tsx
│   └── components/review/
│       ├── index.ts
│       ├── DecisionCard.tsx
│       ├── DecisionList.tsx
│       ├── PRStatusBadge.tsx
│       └── MinutesHeader.tsx
├── stores/
│   └── prReviewStore.ts
├── services/
│   └── prReviewService.ts
└── types/
    └── pr-review.ts
```

### 9.2 Backend

```
backend/app/
├── api/v1/endpoints/
│   └── decisions.py
├── services/
│   └── review_service.py
├── models/kg/
│   └── decision.py
├── schemas/
│   └── review.py
└── repositories/kg/
    └── repository.py (approve_and_merge_if_complete)
```

---

## 10. 에러 처리

| 에러 | 원인 | 처리 |
|------|------|------|
| `DECISION_NOT_FOUND` | 존재하지 않는 Decision | 404 반환 |
| `ALREADY_REVIEWED` | 이미 승인/거부한 Decision | 중복 액션 무시 |
| `NOT_PARTICIPANT` | 회의 참석자가 아닌 사용자 | 403 반환 |
| `MEETING_NOT_FOUND` | 존재하지 않는 회의 | 404 반환 |

---

## 참조

- 워크플로우 명세: [02-workflow-spec.md](../usecase/02-workflow-spec.md)
- LangGraph 워크플로우: [workflows/README.md](../../agent/workflows/README.md)
- 도메인 규칙: [03-domain-rules.md](../domain/03-domain-rules.md)
