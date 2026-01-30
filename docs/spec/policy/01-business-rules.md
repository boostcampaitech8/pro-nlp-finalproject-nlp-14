# MIT 비즈니스 규칙 (Business Rules)

## 범위

이 문서는 변경 가능한 운영 정책을 정의한다.
시스템 수준의 불변식/제약 조건은 `domain/03-domain-rules.md`를 참조한다.

---

## 회의 진행 규칙

### BR-001: 회의 중 Decision Approve 금지

- **규칙**: 회의 진행 중에는 PR 생성 및 Decision approve를 권장하지 않음
- **상태**: 권장 (시스템 강제 아님)
- **강제 수준**: 경고 표시 / 설정으로 차단 가능
- **예외**: 긴급 수정 필요 시 회의 참여자 전원 동의
- **근거**: 회의 중 합의가 완료되지 않은 상태에서 GT 업데이트 방지
- **변경이력**: 2026-01-20 합의, 2026-01-21 Agenda 기반으로 수정, 2026-01-22 Decision 기반으로 수정

### BR-002: 수동 PR 생성

- **규칙**: 회의 없이도 수동으로 PR을 생성할 수 있음
- **조건**: Agent와 대화를 통해 Agenda/Decision 생성 후 PR 오픈
- **용도**: 회의 없이 GT 수정이 필요한 경우 (오류 수정, 보완 등)
- **변경이력**: 2026-01-20 합의, 2026-01-23 Branch -> PR로 수정

---

## 컨텍스트 관리 규칙

### BR-003: Agent 컨텍스트 범위

- **규칙**: 회의 참여 Agent는 모든 "Public한 메시지(음성/채팅)"만 컨텍스트로 가짐
- **세부사항**:
  - Public 음성: 회의 중 모든 발화 (STT 결과)
  - Public 채팅: 회의 채팅방의 모든 메시지
- **제외**: 개인 AI assistant와의 private 대화
- **변경이력**: 2026-01-19 합의

### BR-004: 개인 Assistant 컨텍스트 범위

- **규칙**: 개인 AI assistant는 Public 메시지 + 해당 사용자의 Private 대화 + Tool 호출 결과를 컨텍스트로 가짐
- **세부사항**:
  - Public 메시지: BR-003와 동일
  - Private 대화: 해당 사용자가 assistant에게 보낸/받은 메시지
  - Tool 호출 결과: assistant가 사용자를 위해 호출한 도구 결과
- **변경이력**: 2026-01-19 합의

### BR-005: 미병합 PR 컨텍스트 [TBD]

- **상태**: 논의 필요
- **문제**: 미병합 PR이 있는 상태에서 새 회의 시작 시 컨텍스트를 GT만 사용할지, GT+PR을 선택적으로 포함할지
- **제안 옵션**:
  1. GT만 사용 (기본값)
  2. GT + 특정 PR 선택적 포함
  3. GT + 모든 미병합 PR 포함
- **결정 필요**: 팀 논의 후 확정

---

## 동시 호출 정책

### BR-006: Agent 동시 호출 처리 [TBD]

- **상태**: 논의 필요
- **상황**: 여러 사용자가 동시에 Agent에게 요청
- **현재 제안**:
  - 보이스 호출: 현재 시퀀스 중단 + 새 요청 컨텍스트 추가
  - 채팅 호출: 병렬 처리
- **결정 필요**: 팀 논의 후 확정

### BR-007: Agent 응답 중 추가 요청 [TBD]

- **상태**: 논의 필요
- **상황**: Agent가 응답 중인데 사용자가 추가 요청
- **현재 제안**: 현재 시퀀스 중단 후 컨텍스트에 추가
- **결정 필요**: 팀 논의 후 확정

---

## PR 리뷰 규칙

### BR-008: 리뷰어 지정

- **규칙**: PR open 시 Agent가 각 Decision별로 리뷰어 자동 지정
- **자동 지정 기준**: [TBD] - 관련 팀원 식별 로직
  - 회의 참여자 중 Decision 작성자 제외
  - 관련 결정사항에 이전에 참여한 팀원
- **추가 지정**: Host가 추가 리뷰어 지정 가능
- **변경이력**: 2026-01-21 확정, 2026-01-22 Decision 기반으로 수정

### BR-009: 승인 조건

- **규칙**: Decision이 approved 되려면 지정된 리뷰어 전원의 approval 필요
- **거부 조건**: 리뷰어 1명이라도 reject하면 해당 Decision은 rejected
- **변경이력**: 2026-01-21 확정, 2026-01-22 Decision 기반으로 수정

---

## 데이터 보존 규칙

### BR-010: Transcript 보존

- **규칙**: 회의 transcript는 영구 보존
- **근거**: 결정사항의 근거 자료로 활용
- **삭제**: 팀 삭제 시에만 삭제 (cascade)

### BR-011: Recording 보존

- **규칙**: 회의 녹음 파일 보존 기간
- **기본값**: [TBD] - 90일 / 영구 / 팀별 설정
- **스토리지**: MinIO (S3 호환)

### BR-012: PR 이력 보존

- **규칙**: PR 및 리뷰 코멘트는 영구 보존
- **근거**: GT 변경 이력의 무결성 보장

---

## 가시성 옵션

### BR-013: Agent 작업 결과 가시성

- **규칙**: 채팅으로 Agent를 호출할 경우 작업 결과의 가시성 옵션 제공
- **옵션**:
  - Public: 다른 참여자에게도 보임
  - Private: 요청자에게만 보임 (기본값)
- **변경이력**: 2026-01-19 논의

---

## Agenda 관련 규칙

### BR-014: Agenda 식별 방식

- **규칙**: 새 Agenda 생성 시 AI가 기존 Agenda와 semantic matching 수행
- **방식**: 임베딩 벡터 유사도 비교
- **임계값**: [TBD] - 유사도 threshold
- **처리 방식**:
  - 유사 Agenda 발견 시: 기존 Agenda에 연결 (사용자 확인 요청)
  - 유사 Agenda 없음: 새 Agenda 생성
- **변경이력**: 2026-01-21 신규

### BR-015: Decision별 부분 Approve/Reject

- **규칙**: PR 내 Decision별로 독립적 approve/reject 가능
- **세부사항**:
  - approved Decision은 즉시 GT 반영
  - rejected Decision은 rejected 상태로 변경
  - 부분 처리 가능 (일부 approve, 일부 reject)
- **변경이력**: 2026-01-21 신규, 2026-01-22 Decision 기반으로 수정

### BR-016: PR 자동 Close 조건

- **규칙**: PR 내 모든 Decision이 처리(approved 또는 rejected)되면 자동 close
- **세부사항**:
  - 수동 close 불필요 (자동 처리)
  - close 시점에 Meeting 상태도 confirmed로 변경
- **변경이력**: 2026-01-21 신규, 2026-01-22 Decision 기반으로 수정

### BR-017: Rejected Decision 재제안

- **규칙**: rejected된 Decision은 새 회의에서 새로운 Decision으로 재제안 가능
- **세부사항**:
  - 기존 rejected Decision은 이력으로 보존
  - 새 Decision은 같은 Agenda에 연결
  - 재제안 시 이전 rejected 사유 참조 가능
- **변경이력**: 2026-01-21 신규

---

## 참조

- 도메인 규칙: [domain/03-domain-rules.md](../domain/03-domain-rules.md)
- 권한 정책: [policy/02-access-policy.md](02-access-policy.md)
