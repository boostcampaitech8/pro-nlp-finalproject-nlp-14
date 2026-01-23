# MIT 워크플로우 명세 (Workflow Spec)

## 범위

이 문서는 주요 프로세스의 흐름과 상태 전이를 정의한다.

---

## WF-001: 회의 -> GT 업데이트 플로우

### 전체 흐름

```
┌──────────────────────────────────────────────────────────────────────┐
│                    회의 -> GT 업데이트 워크플로우                      │
└──────────────────────────────────────────────────────────────────────┘

[회의 시작]
     │
     ▼
┌─────────────┐
│  scheduled  │ Meeting.status
└──────┬──────┘
       │ startMeeting()
       │ [UC-003]
       ▼
┌─────────────┐
│   ongoing   │
└──────┬──────┘
       │
       │              ┌──────────────────────────────────┐
       │              │ 실시간 처리                       │
       │              │ - VAD: 발화 감지                  │
       │              │ - STT: 실시간 텍스트 변환         │
       │              │ - Recording: 서버 녹음           │
       │              │ - Agent: 실시간 지원              │
       │              └──────────────────────────────────┘
       │
       │ endMeeting()
       │ [UC-004]
       ▼
┌─────────────┐     ┌──────────────────────────────────┐
│  completed  │────▶│ 후처리 (비동기)                   │
└──────┬──────┘     │ 1. Recording 파일 저장           │
       │            │ 2. Transcript 생성 (정제 STT)     │
       │            │ 3. Minutes 초안 생성 (Agent)      │
       │            │ 4. Agenda 추출 (semantic matching)│
       │            │ 5. 각 Agenda에 Decision 생성      │
       │            └──────────────────────────────────┘
       │                        │
       │                        ▼
       │              ┌──────────────────────────────────┐
       │              │ Agent가 PR 자동 오픈             │
       │              │ - DecisionReview 생성 (각 Decision)│
       │              │ - 리뷰어 자동 지정 [BR-008]      │
       │              │ - 팀원 알림                       │
       │              └──────────────────────────────────┘
       │
       │ PR 생성 완료
       ▼
┌─────────────┐     ┌──────────────────────────────────┐
│  in_review  │────▶│ Decision별 리뷰 프로세스          │
└──────┬──────┘     │ - Comment/Suggestion 추가        │
       │            │ - Decision별 approve/reject      │
       │            │ - approved -> 즉시 GT 반영        │
       │            │ - Agent가 GT 대조 지원            │
       │            └──────────────────────────────────┘
       │
       │ 모든 Decision 처리 완료
       │ (approved 또는 rejected)
       ▼
┌─────────────┐     ┌──────────────────────────────────┐
│  confirmed  │────▶│ PR 자동 close                     │
└─────────────┘     │ - approved Decision -> latest    │
                    │ - rejected Decision -> rejected  │
                    │ - GT: Knowledge graph 업데이트   │
                    │ - 팀원 알림                       │
                    └──────────────────────────────────┘
```

### 상태 전이 테이블

| 현재 상태 | 이벤트 | 다음 상태 | 트리거 | 조건 |
|-----------|--------|-----------|--------|------|
| scheduled | startMeeting | ongoing | Host | - |
| scheduled | cancelMeeting | cancelled | Host | - |
| ongoing | endMeeting | completed | Host | - |
| ongoing | cancelMeeting | cancelled | Host | - |
| completed | PR 생성 | in_review | System(Agent) | Transcript, Agenda 추출 완료 |
| in_review | 모든 Decision 처리 | confirmed | System | 모든 DecisionReview가 approved 또는 rejected |
| in_review | closePR (수동) | completed | Host/Admin | 예외 상황 |

---

## WF-002: PR 및 Decision 리뷰 플로우

### PR 상태 다이어그램

```
                    ┌─────────────────────────┐
                    │         open            │
                    │    (PR 생성 직후)        │
                    │  DecisionReview 생성됨  │
                    └───────────┬─────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │       in_review         │
                    │  (Decision별 리뷰 진행)  │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
        ┌──────────┐      ┌──────────┐      ┌──────────┐
        │Decision A│      │Decision B│      │Decision C│
        │ approved │      │ rejected │      │ pending  │
        │ -> GT    │      │          │      │          │
        └──────────┘      └──────────┘      └──────────┘
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ 모든 Decision 처리 완료? │
                    └───────────┬─────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                   Yes                     No
                    │                       │
                    ▼                       │
              ┌──────────┐                  │
              │  closed  │                  │
              │ (자동)   │◀─────────────────┘
              └──────────┘        (계속 리뷰 진행)
```

### Decision 리뷰 상태 다이어그램

```
              ┌──────────┐
              │ pending  │ (DecisionReview 생성 직후)
              └────┬─────┘
                   │
         ┌─────────┼─────────┐
         │         │         │
         ▼         ▼         ▼
   ┌──────────┐ ┌──────────┐
   │ comment  │ │ approve  │
   │ 추가     │ │ 요청     │
   └────┬─────┘ └────┬─────┘
        │            │
        │            ▼
        │      ┌──────────┐
        │      │필수 승인 │
        │      │충족 여부 │
        │      └────┬─────┘
        │           │
        │     ┌─────┴─────┐
        │     │           │
        │   Yes          No
        │     │           │
        │     ▼           │
        │ ┌──────────┐    │
        │ │ approved │    │
        │ │-> GT 반영│    │
        │ │ (즉시)   │    │
        │ └──────────┘    │
        │                 │
        └────────┬────────┘
                 │
                 ▼
           ┌──────────┐
           │ rejected │ (reject 요청 시)
           │          │
           └──────────┘
```

### PR 상태 정의

| 상태 | 설명 | 가능한 액션 |
|------|------|------------|
| open | PR 생성 직후 | Decision 리뷰 시작 |
| in_review | Decision별 리뷰 진행 중 | comment, Decision approve/reject |
| closed | 모든 Decision 처리 완료 | - (최종 상태) |

### DecisionReview 상태 정의

| 상태 | 설명 | 효과 |
|------|------|------|
| pending | 리뷰 대기 중 | Decision 상태: draft |
| approved | 승인됨 | Decision 상태: latest, 즉시 GT 반영 |
| rejected | 거부됨 | Decision 상태: rejected |

---

## WF-003: Decision 상태 파생 플로우

### 상태 파생 로직

```
┌─────────────────────────────────────────────────────────────────┐
│                    Decision 상태 파생                             │
└─────────────────────────────────────────────────────────────────┘

Decision 조회 요청
        │
        ▼
┌───────────────────────────────────────┐
│ 해당 Decision의 DecisionReview 조회    │
└─────────────────┬─────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
  DecisionReview      DecisionReview
     없음                 있음
        │                   │
        ▼                   ▼
    [draft]        ┌────────────────────┐
                   │DecisionReview.status│
                   │ 확인               │
                   └─────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
     pending             approved              rejected
        │                    │                    │
        ▼                    │                    ▼
    [draft]                  │               [rejected]
                             ▼
                   ┌──────────────────────┐
                   │ 같은 Agenda의 다른   │
                   │ Decision 존재 확인   │
                   └─────────┬────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
           더 최신 있음          최신임
                    │                 │
                    ▼                 ▼
               [outdated]        [latest]
```

### 파생 규칙 (의사 코드)

```python
def derive_decision_status(decision):
    decision_review = get_decision_review_for_decision(decision)

    if decision_review is None:
        return 'draft'

    if decision_review.status == 'pending':
        return 'draft'

    if decision_review.status == 'rejected':
        return 'rejected'

    if decision_review.status == 'approved':
        # 같은 Agenda의 더 최신 decision이 있는지 확인
        newer_decisions = get_decisions_for_agenda(
            decision.agenda_id,
            approved_after=decision_review.approved_at
        )
        if newer_decisions:
            return 'outdated'
        return 'latest'
```

### 상태 전이 규칙

| 현재 상태 | 이벤트 | 다음 상태 |
|-----------|--------|-----------|
| draft | Decision approve | latest |
| draft | Decision reject | rejected |
| latest | 새 Decision approved (같은 Agenda) | outdated |
| rejected | - | - (최종 상태, 재제안 시 새 Decision 생성) |
| outdated | - | - (최종 상태) |

---

## WF-004: Agent 요청 처리 플로우

### 처리 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 요청 처리 플로우                           │
└─────────────────────────────────────────────────────────────────┘

사용자 요청 (음성/텍스트)
        │
        ▼
┌───────────────────────────────────────┐
│           STT (음성인 경우)              │
└─────────────────┬─────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────┐
│           의도 분석 (Intent)            │
│   - 질문/명령/요청 구분                   │
│   - 대상 엔티티 식별                      │
└─────────────────┬─────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────┐
│           도구 선택 (Tool Selection)    │
│   - mit_blame, mit_search, ...        │
│   - mcp_jira, mcp_slack, ...          │
└─────────────────┬─────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────┐
│           도구 실행                     │
│   - 파라미터 추출                        │
│   - API 호출                           │
│   - 결과 수집                           │
└─────────────────┬─────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────┐
│           응답 생성                     │
│   - 결과 정리                           │
│   - 자연어 변환                          │
└─────────────────┬─────────────────────┘
                  │
                  ▼
┌───────────────────────────────────────┐
│           응답 전달                      │
│   - 텍스트 출력                          │
│   - TTS (음성 출력, 선택적)               │
└───────────────────────────────────────┘
```

---

## WF-005: Agenda 식별 플로우

### Agenda 추출 및 식별 로직

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agenda 식별 플로우                             │
└─────────────────────────────────────────────────────────────────┘

회의 종료 -> Minutes 생성
        │
        ▼
┌───────────────────────────────────────┐
│ Agent가 Minutes에서 안건 추출          │
│ - 논의된 주제 식별                      │
│ - 각 주제에 대한 결정 내용 추출          │
└─────────────────┬─────────────────────┘
                  │
                  ▼ (각 추출된 안건에 대해)
┌───────────────────────────────────────┐
│ 기존 Agenda와 semantic matching        │
│ - 팀의 모든 Agenda 임베딩 검색          │
│ - 유사도 계산                          │
└─────────────────┬─────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
  유사 Agenda         유사 Agenda
    발견                 없음
        │                   │
        ▼                   ▼
┌──────────────────┐ ┌──────────────────┐
│ 사용자 확인 요청  │ │ 새 Agenda 생성   │
│ "기존 안건과     │ │ - topic 저장     │
│  연결할까요?"    │ │ - embedding 생성 │
└────────┬─────────┘ └────────┬─────────┘
         │                    │
    ┌────┴────┐               │
    │         │               │
   예        아니오            │
    │         │               │
    ▼         ▼               │
[기존      [새 Agenda         │
 Agenda     생성]             │
 연결]        │               │
    │         └───────────────┤
    │                         │
    └─────────────┬───────────┘
                  │
                  ▼
┌───────────────────────────────────────┐
│ Decision 생성                          │
│ - agenda_id 연결                       │
│ - content, context 저장               │
│ - transcript_refs 연결                │
└───────────────────────────────────────┘
```

### Semantic Matching 규칙

| 유사도 | 처리 |
|--------|------|
| >= threshold (TBD) | 기존 Agenda 후보로 표시, 사용자 확인 |
| < threshold | 새 Agenda 생성 |

---

## 프로세스 규칙 요약

| 규칙 | 설명 | 참조 |
|------|------|------|
| 회의 중 Decision approve 금지 | 회의 진행 중 Decision approve 권장하지 않음 | BR-001 |
| PR 자동 생성 | 회의 종료 후 Agent가 PR 자동 생성 (Agenda/Decision 추출 포함) | UC-004 |
| 상태 파생 | Decision 상태는 DecisionReview 상태에서 파생 | INV-002 |
| GT 불변성 | GT는 Decision approve로만 변경 | INV-003 |
| 부분 merge | PR 내 Decision별 독립적 approve/reject 가능 | BR-015 |
| 자동 close | 모든 Decision 처리 시 PR 자동 close | BR-016 |
| Agenda 식별 | AI semantic matching으로 동일 Agenda 식별 | BR-014 |

---

## 참조

- 유즈케이스: [usecase/01-usecase-specs.md](01-usecase-specs.md)
- 도메인 규칙: [domain/03-domain-rules.md](../domain/03-domain-rules.md)
- 비즈니스 규칙: [policy/01-business-rules.md](../policy/01-business-rules.md)
