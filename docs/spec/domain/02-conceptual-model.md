# MIT 개념 모델 (Conceptual Model)

## 범위

이 문서는 MIT 프로젝트의 엔티티, 관계, 속성 및 각 엔티티의 책임을 정의한다.

---

## 엔티티 관계도

```
┌─────────────────────────────────────────────────────────────────────┐
│                             Team                                     │
│  - id, name, description, created_by, created_at                    │
└───────────────────────────────┬─────────────────────────────────────┘
          │                     │
          │ N:M                 │ 1:N
          │ (via TeamMember)    │
          ▼                     ▼
┌───────────────────┐   ┌─────────────────────────────────────────────┐
│       User        │   │                   Meeting                    │
│  - id, email      │   │  - id, title, status, scheduled_at          │
│  - name           │   │  - started_at, ended_at, team_id            │
└───────────────────┘   └───────────────────────────────────┬─────────┘
          │                         │           │           │
          │                         │           │           │
          │                         ▼           ▼           ▼
          │                   ┌──────────┐ ┌──────────┐ ┌──────────┐
          │                   │Recording │ │Transcript│ │  Branch  │
          │                   │  - id    │ │  - id    │ │  - id    │
          │                   │  - path  │ │  - text  │ │  - base  │
          │                   └──────────┘ └──────────┘ └────┬─────┘
          │                                                   │
          └───────────────────────────────────────────────────┤
                                                              │ 1:1
                                                              ▼
                                                        ┌──────────┐
                                                        │ Minutes  │
                                                        │  - id    │
                                                        │  - summary│
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
                                                        │ (main)   │
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

### Branch

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| meeting_id | UUID (FK) | 회의 ID |
| base_gt_version | UUID | 파생 시점의 GT 버전 |
| status | enum | active / merged / closed |
| created_at | datetime | 생성 시각 |

**책임**: 회의별 작업 공간을 제공하고 GT로부터의 파생을 추적한다.

### Minutes (회의록)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| branch_id | UUID (FK) | 브랜치 ID |
| meeting_id | UUID (FK) | 회의 ID |
| summary | text | 회의 요약 |
| created_by | UUID (FK) | 작성자 (Agent 또는 User) |
| created_at | datetime | 생성 시각 |
| updated_at | datetime | 수정 시각 |

**책임**: 회의 결과를 요약하고 Decision을 포함하여 GT 업데이트의 단위로 작동한다.

### Decision (결정사항)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| minutes_id | UUID (FK) | 회의록 ID |
| topic | string | 안건/주제 [TBD: 식별 방법] |
| content | text | 결정 내용 |
| context | text | 결정 맥락/사유 |
| transcript_refs | JSONB | 근거 발화 참조 (utterance IDs) |
| created_at | datetime | 생성 시각 |

**책임**: 합의된 사실/선택을 저장하고 GT의 구성 요소로 작동한다.

**[TBD]**: `topic` 필드를 통한 "동일 안건 식별" 알고리즘 (Embedding / 키워드 / LLM 기반)

### PR (Pull Request)

| 속성 | 타입 | 설명 |
|------|------|------|
| id | UUID | 고유 식별자 |
| branch_id | UUID (FK) | 브랜치 ID |
| title | string | PR 제목 |
| description | text | PR 설명 |
| status | enum | open / in_review / approved / merged / closed |
| author_id | UUID (FK) | 작성자 (Agent 또는 User) |
| reviewers | JSONB | 리뷰어 목록 |
| created_at | datetime | 생성 시각 |
| merged_at | datetime | 병합 시각 |
| merged_by | UUID (FK) | 병합자 |

**책임**: 브랜치의 회의록을 GT로 병합하는 리뷰/합의 절차를 관리한다.

### GT (Ground Truth)

**[TBD]**: 구체적인 저장 구조 (그래프 DB / 관계형 DB / 하이브리드)

| 속성 | 타입 | 설명 |
|------|------|------|
| version | UUID | GT 버전 |
| decisions | array | 최신 Decision 목록 |
| updated_at | datetime | 마지막 업데이트 시각 |
| updated_by_pr | UUID (FK) | 마지막 업데이트 PR |

**책임**: 팀이 현재 합의한 최신 결정의 집합을 유지하고 조회 가능하게 한다.

---

## 상태 파생 규칙

Decision의 상태는 자체 저장하지 않고 다음 규칙으로 파생:

```
IF PR.status == 'merged' AND PR.merged_at == max(all merged PRs for same topic):
    Decision.derived_status = 'latest'
ELIF PR.status IN ('open', 'in_review', 'approved'):
    Decision.derived_status = 'draft'
ELSE:
    Decision.derived_status = 'outdated'
```

---

## 카디널리티 요약

| 관계 | 카디널리티 | 설명 |
|------|------------|------|
| Team - User | M:N (via TeamMember) | 사용자는 여러 팀에 속할 수 있음 |
| Team - Meeting | 1:N | 팀은 여러 회의를 가짐 |
| Meeting - Participant | 1:N | 회의는 여러 참여자를 가짐 |
| Meeting - Recording | 1:N | 회의는 여러 녹음을 가질 수 있음 |
| Meeting - Transcript | 1:1 | 회의당 하나의 최종 transcript |
| Meeting - Branch | 1:1 | 회의당 하나의 브랜치 |
| Branch - Minutes | 1:1 | 브랜치당 하나의 회의록 |
| Minutes - Decision | 1:N | 회의록은 여러 결정을 포함 |
| Branch - PR | 1:1 | 브랜치당 하나의 PR |
