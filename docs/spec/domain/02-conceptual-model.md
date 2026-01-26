# MIT 개념 모델 (Conceptual Model)

## 범위

이 문서는 MIT 프로젝트의 엔티티, 관계, 속성 및 각 엔티티의 책임을 정의한다.

---

## 엔티티 관계도

```
┌─────────────────────────────────────────────────────────────────────┐
│                             Team                                     │
│  - id, name, description, created_by, created_at                    │
└───────────────────────────────┬──────────────────┬──────────────────┘
          │                     │                  │
          │ N:M                 │ 1:N              │ 1:N
          │ (via TeamMember)    │                  │
          ▼                     ▼                  ▼
┌───────────────────┐   ┌─────────────────┐  ┌──────────────────────┐
│       User        │   │     Meeting     │  │       Agenda         │
│  - id, email      │   │  - id, title    │  │  - id, topic         │
│  - name           │   │  - status       │  │  - embedding         │
└───────────────────┘   └────────┬────────┘  │  - team_id           │
          │                      │           └──────────┬───────────┘
          │            ┌─────────┼─────────┐            │
          │            │         │         │            │ 1:N
          │            ▼         ▼         ▼            │
          │      ┌──────────┐ ┌──────────┐ ┌──────────┐ │
          │      │Recording │ │Transcript│ │ Minutes  │ │
          │      │  - id    │ │  - id    │ │  - id    │ │
          │      │  - path  │ │  - text  │ │ - summary│ │
          │      └──────────┘ └──────────┘ └────┬─────┘ │
          │                                     │       │
          └─────────────────────────────────────┤       │
                                                │ M:N   │
                                                │(via MinutesAgenda)
                                                ▼       │
                                          ┌──────────┐  │
                                          │  Agenda  │◀─┘
                                          │ (참조)   │
                                          └────┬─────┘
                                               │ 1:N
                                               ▼
                                          ┌──────────┐
                                          │ Decision │
                                          │  - id    │
                                          │  - content│
                                          └────┬─────┘
                                               │
                                               ▼
                                          ┌──────────┐
                                          │    GT    │
                                          │(Knowledge│
                                          │  Graph)  │
                                          └──────────┘
```

---

## 엔티티 정의

### Team

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| name | string | 팀 이름 |
| description | string | 팀 설명 |
| created_by | UUID (FK) | 생성자 User ID |
| created_at | datetime | 생성 시각 |

**책임**: 조직 단위를 관리하고 회의와 GT의 소유권을 정의한다.

### User

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| email | string | 이메일 (unique) |
| name | string | 사용자 이름 |
| auth_provider | string | 인증 제공자 (google, github 등) |
| created_at | datetime | 가입 시각 |

**책임**: 인증 및 참여자 식별의 기본 단위이다.

### TeamMember

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| team_id | UUID (FK) | 팀 ID |
| user_id | UUID (FK) | 사용자 ID |
| role | enum | owner / admin / member |
| joined_at | datetime | 가입 시각 |

**책임**: 팀과 사용자 간의 관계 및 권한을 정의한다.

### Meeting

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| team_id | UUID (FK) | 소속 팀 ID |
| title | string | 회의 제목 |
| description | string | 회의 설명 |
| status | enum | 회의 상태 |
| scheduled_at | datetime | 예정 시각 |
| started_at | datetime | 시작 시각 |
| ended_at | datetime | 종료 시각 |
| created_by | UUID (FK) | 생성자 User ID |

**상태 (MeetingStatus)**:
- `scheduled`: 예정됨
- `ongoing`: 진행 중
- `completed`: 완료됨
- `in_review`: 리뷰 중 (PR 오픈)
- `confirmed`: 확정됨 (GT 반영)
- `cancelled`: 취소됨

**책임**: 회의 세션의 생명주기를 관리한다.

### Agenda (안건)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| team_id | UUID (FK) | 팀 ID |
| topic | string | 안건 주제 |
| embedding | vector | semantic matching용 임베딩 |
| created_at | datetime | 최초 생성 시각 |
| created_by_meeting | UUID (FK) | 최초 생성 회의 ID |

**책임**: 팀 전체에서 공유되는 안건을 관리하고, semantic matching을 통해 동일 안건 식별을 지원한다.

### MinutesAgenda (회의록-안건 연결)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| minutes_id | UUID (FK) | 회의록 ID |
| agenda_id | UUID (FK) | 안건 ID |
| created_at | datetime | 연결 시각 |

**책임**: 회의록과 안건 간의 M:N 관계를 관리한다.

### MeetingParticipant

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| meeting_id | UUID (FK) | 회의 ID |
| user_id | UUID (FK) | 사용자 ID |
| role | enum | host / participant |
| joined_at | datetime | 참여 시각 |
| left_at | datetime | 퇴장 시각 |

**책임**: 회의 참여자 및 역할을 관리한다.

### Recording

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| meeting_id | UUID (FK) | 회의 ID |
| file_path | string | 저장 경로 (MinIO) |
| status | enum | recording / completed / failed |
| duration | integer | 녹음 길이 (초) |
| created_at | datetime | 생성 시각 |

**책임**: 회의 음성 녹음 파일을 관리한다.

### Transcript

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| meeting_id | UUID (FK) | 회의 ID |
| full_text | text | 전체 텍스트 |
| utterances | JSONB | 발화 목록 (speaker, text, start, end) |
| status | enum | pending / processing / completed / failed |
| created_at | datetime | 생성 시각 |

**책임**: 발화 기록(STT 결과)을 저장하고 회의록의 근거 자료로 제공한다.

### Minutes (회의록)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| meeting_id | UUID (FK) | 회의 ID |
| summary | text | 회의 요약 |
| created_by | UUID (FK) | 작성자 (Agent 또는 User) |
| created_at | datetime | 생성 시각 |
| updated_at | datetime | 수정 시각 |

**책임**: 회의 결과를 요약하고 Agenda와 Decision 추출의 원천으로 작동한다.

### Decision (결정사항)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| agenda_id | UUID (FK) | 안건 ID |
| minutes_id | UUID (FK) | 회의록 ID (생성 출처) |
| content | text | 결정 내용 |
| context | text | 결정 맥락/사유 |
| transcript_refs | JSONB | 근거 발화 참조 (utterance IDs) |
| created_at | datetime | 생성 시각 |

**책임**: 특정 Agenda에 대해 합의된 사실/선택을 저장하고 GT의 구성 요소로 작동한다.

**상태 (파생)**: Decision 상태는 자체 저장하지 않고 DecisionReview 상태로 파생
- `draft`: PR에 존재하지만 아직 approved되지 않음
- `latest`: Decision이 approved되어 GT에 반영됨
- `rejected`: 리뷰에서 거부됨 (합의 실패)
- `outdated`: 이후 Decision에 의해 대체됨

### PR (Pull Request)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| meeting_id | UUID (FK) | 회의 ID |
| title | string | PR 제목 |
| description | text | PR 설명 |
| status | enum | open / in_review / closed |
| author_id | UUID (FK) | 작성자 (Agent 또는 User) |
| created_at | datetime | 생성 시각 |
| closed_at | datetime | 종료 시각 |

**책임**: 회의의 Decision들을 GT로 병합하는 리뷰/합의 절차를 관리한다. Decision별 부분 approve/merge를 지원한다.

**종료 조건**: 모든 Decision이 처리(approved 또는 rejected)되면 자동 close

### DecisionReview (결정별 리뷰)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| pr_id | UUID (FK) | PR ID |
| decision_id | UUID (FK) | 결정 ID |
| status | enum | pending / approved / rejected |
| approved_at | datetime | 승인 시각 (전원 approve 시) |
| rejected_at | datetime | 거부 시각 (1명이라도 reject 시) |
| rejected_by | UUID (FK) | 거부한 리뷰어 ID |
| reject_reason | text | 거부 사유 |

**책임**: PR 내 각 Decision에 대한 리뷰 상태를 관리하고, 전원 approve 시 해당 Decision을 GT에 반영한다.

**상태 결정 규칙**:
- `pending`: 아직 모든 리뷰어가 응답하지 않음
- `approved`: 지정된 리뷰어 전원이 approve
- `rejected`: 리뷰어 1명이라도 reject (즉시 확정)

### ReviewerApproval (리뷰어별 승인)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| decision_review_id | UUID (FK) | DecisionReview ID |
| reviewer_id | UUID (FK) | 리뷰어 User ID |
| status | enum | pending / approved / rejected |
| assigned_by | enum | agent / host |
| assigned_at | datetime | 지정 시각 |
| responded_at | datetime | 응답 시각 |

**책임**: 각 리뷰어의 개별 승인/거부 상태를 관리한다.

### GT (Ground Truth)

**구조**: Knowledge graph로 구성, Decision 이력 포함

**[TBD]**: 구체적인 저장 구조 (그래프 DB / 관계형 DB / 하이브리드)

| 속성 | 타입 | 설명 |
|------|------|------|
| version | UUID | GT 버전 |
| agendas | array | Agenda 목록 (각 Agenda의 latest Decision 포함) |
| decision_history | graph | Decision 이력 (Knowledge graph) |
| updated_at | datetime | 마지막 업데이트 시각 |
| updated_by_agenda | UUID (FK) | 마지막 업데이트 Agenda |

**책임**: 팀이 현재 합의한 최신 결정의 집합을 유지하고, Agenda별 Decision 이력을 추적한다.

**업데이트 단위**: Agenda (PR 내 Agenda별 부분 merge 가능)

---

## 상태 파생 규칙

Decision의 상태는 자체 저장하지 않고 다음 규칙으로 파생:

```
IF DecisionReview.status == 'approved':
    IF Decision.approved_at == max(all approved Decisions for same Agenda):
        Decision.derived_status = 'latest'
    ELSE:
        Decision.derived_status = 'outdated'
ELIF DecisionReview.status == 'rejected':
    Decision.derived_status = 'rejected'
ELSE:  # DecisionReview.status == 'pending'
    Decision.derived_status = 'draft'
```

**상태 전이**:
- `draft` -> `latest`: Decision이 approved될 때
- `draft` -> `rejected`: Decision이 rejected될 때
- `latest` -> `outdated`: 같은 Agenda에 대해 새로운 Decision이 approved될 때

---

## 카디널리티 요약

| 관계 | 카디널리티 | 설명 |
|------|------------|------|
| Team - User | M:N (via TeamMember) | 사용자는 여러 팀에 속할 수 있음 |
| Team - Meeting | 1:N | 팀은 여러 회의를 가짐 |
| Team - Agenda | 1:N | 팀은 여러 안건을 가짐 |
| Meeting - Participant | 1:N | 회의는 여러 참여자를 가짐 |
| Meeting - Recording | 1:N | 회의는 여러 녹음을 가질 수 있음 |
| Meeting - Transcript | 1:1 | 회의당 하나의 최종 transcript |
| Meeting - Minutes | 1:1 | 회의당 하나의 회의록 |
| Meeting - PR | 1:1 | 회의당 하나의 PR |
| Minutes - Agenda | M:N (via MinutesAgenda) | 회의록은 여러 안건을 포함, 안건은 여러 회의에서 논의 |
| Agenda - Decision | 1:N | 안건은 여러 결정을 가짐 (회의별로 축적) |
| PR - DecisionReview | 1:N | PR은 여러 결정 리뷰를 포함 |
| DecisionReview - ReviewerApproval | 1:N | 결정 리뷰는 여러 리뷰어 승인을 포함 |

---

## 연결 엔티티와 행위 매핑

다음 엔티티들은 핵심 엔티티 간의 관계를 관리하고 특정 행위를 지원한다.

| 엔티티 | 연결 대상 | 지원하는 행위 |
|--------|-----------|---------------|
| MinutesAgenda | Minutes <-> Agenda | 회의록에서 안건 추출, 안건별 회의록 조회 |
| DecisionReview | PR <-> Decision | Decision별 승인/거부 프로세스 관리 |
| ReviewerApproval | DecisionReview <-> User | 리뷰어별 개별 승인 상태 추적 |
| MeetingParticipant | Meeting <-> User | 회의 참여자 역할 및 참여 시간 관리 |
| TeamMember | Team <-> User | 팀 멤버십 및 역할 권한 관리 |
