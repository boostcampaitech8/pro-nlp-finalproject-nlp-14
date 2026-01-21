# MIT 도메인 규칙 카탈로그 (Domain Rules)

## 범위

이 문서는 MIT 시스템의 불변식(Invariants)과 제약 조건(Constraints)을 정의한다.
변경 가능한 운영 정책은 `policy/01-business-rules.md`를 참조한다.

---

## 불변식 (Invariants)

불변식은 시스템 전체에서 항상 참이어야 하는 규칙이다.

### INV-001: 회의당 브랜치 단일성

- **규칙**: 하나의 회의는 정확히 하나의 브랜치를 생성한다
- **표현**: `Meeting:Branch = 1:1`
- **근거**: 병합 충돌 방지, 단순한 이력 관리
- **위반 시**: 시스템 오류 (브랜치 생성 거부)

### INV-002: 결정 상태 파생

- **규칙**: 결정의 상태(latest/draft/outdated)는 결정 자체에 저장하지 않고, 회의록의 merge 상태와 시점에 의해 파생된다
- **표현**: `Decision.status = f(PR.status, PR.merged_at)`
- **근거**: 상태 불일치 방지, 단일 진실 소스
- **위반 시**: 해당 없음 (저장하지 않으므로)

> **구현 참고 (Computed Field 패턴)**
>
> "파생"은 **값의 원천(source of truth)이 PR 상태**라는 의미이다.
> 성능을 위해 DB에 status 컬럼을 캐싱할 수 있지만, 다음 규칙을 따라야 한다:
>
> | 허용 | 금지 |
> |------|------|
> | PR 머지 이벤트 시 status 갱신 | 사용자/API가 직접 status UPDATE |
> | 조회 시 캐시된 값 반환 | status 값을 임의로 설정 |
>
> 즉, **저장하되 직접 수정 금지** - 값은 항상 PR 이벤트로부터 계산되어 갱신된다.

### INV-003: GT 불변성

- **규칙**: GT(main)는 직접 수정 불가, 반드시 PR을 통해서만 변경
- **표현**: `GT.update() requires PR.merge()`
- **근거**: 합의 프로세스 보장, 변경 이력 추적
- **위반 시**: 시스템 오류 (직접 수정 API 없음)

### INV-004: 회의록-회의 1:1 관계

- **규칙**: 하나의 회의는 정확히 하나의 회의록을 생성한다
- **표현**: `Meeting:Minutes = 1:1`
- **근거**: 회의 결과의 일관성, GT 업데이트 단위 명확화
- **위반 시**: 시스템 오류 (회의록 생성 거부)

### INV-005: PR은 merge 후 수정 불가

- **규칙**: merge된 PR의 내용은 수정할 수 없다
- **표현**: `IF PR.status == 'merged' THEN PR.is_immutable = true`
- **근거**: GT 이력의 무결성 보장
- **위반 시**: 시스템 오류 (수정 거부)

---

## 제약 조건 (Constraints)

제약 조건은 특정 작업 수행 시 검증되는 규칙이다.

### CON-001: PR 승인 조건

- **규칙**: PR merge는 지정된 리뷰어의 approval 필요
- **조건**: `PR.reviewers.filter(approved).count >= required_approvals`
- **기본값**: required_approvals = 1 [TBD: 팀별 설정 가능]
- **위반 시**: 409 Conflict - "Approval required"

### CON-002: 회의 시작 조건

- **규칙**: 회의 시작은 host만 가능
- **조건**: `current_user.role == 'host'`
- **위반 시**: 403 Forbidden

### CON-003: 회의 종료 조건

- **규칙**: 회의 종료는 host만 가능
- **조건**: `current_user.role == 'host' AND meeting.status == 'ongoing'`
- **위반 시**: 403 Forbidden / 400 Bad Request

### CON-004: Branch 상태 전이

- **규칙**: Branch 상태는 정해진 순서로만 전이
- **허용 전이**:
  ```
  active -> merged (via PR merge)
  active -> closed (via PR close or meeting cancel)
  ```
- **위반 시**: 400 Bad Request - "Invalid state transition"

### CON-005: Meeting 상태 전이

- **규칙**: Meeting 상태는 정해진 순서로만 전이
- **허용 전이**:
  ```
  scheduled -> ongoing (startMeeting)
  scheduled -> cancelled (cancelMeeting)
  ongoing -> completed (endMeeting)
  ongoing -> cancelled (cancelMeeting)
  completed -> in_review (openPR)
  in_review -> confirmed (mergePR)
  in_review -> completed (closePR)
  ```
- **위반 시**: 400 Bad Request - "Invalid state transition"

### CON-006: Decision은 Minutes에 종속

- **규칙**: Decision은 반드시 Minutes에 속해야 함
- **조건**: `Decision.minutes_id IS NOT NULL`
- **위반 시**: 400 Bad Request - "Decision must belong to Minutes"

### CON-007: PR 생성은 회의 종료 후에만 가능

- **규칙**: 회의에 대한 PR은 해당 회의가 종료(회의록 생성)된 후에만 생성 가능
- **조건**: `Meeting.status IN ('completed', 'in_review', 'confirmed')`
- **근거**: 회의록이 존재해야 PR 대상이 됨
- **위반 시**: 400 Bad Request - "Meeting must be completed before creating PR"

---

## 도메인 규칙 vs 비즈니스 규칙

| 구분 | 도메인 규칙 (이 문서) | 비즈니스 규칙 (policy/) |
|------|----------------------|------------------------|
| 변경 가능성 | 시스템 설계 수준, 변경 어려움 | 운영 정책, 변경 가능 |
| 예시 | "회의당 1 브랜치" | "회의 중 PR 금지" |
| 강제 방식 | 시스템 오류 (API 거부) | 경고 또는 설정 가능 |

---

## 참조

- 운영 정책: [policy/01-business-rules.md](../policy/01-business-rules.md)
- 개념 모델: [domain/02-conceptual-model.md](02-conceptual-model.md)
