# MIT 권한 및 가시성 정책 (Access Policy)

## 범위

이 문서는 역할별 권한과 데이터 가시성 정책을 정의한다.

---

## 팀 역할 (Team Roles)

### 역할 정의

| 역할 | 설명 |
|------|------|
| owner | 팀 소유자, 최고 권한 |
| admin | 팀 관리자 |
| member | 일반 팀원 |

### 권한 매트릭스

| 작업 | owner | admin | member |
|------|:-----:|:-----:|:------:|
| 팀 삭제 | O | X | X |
| 팀 설정 변경 | O | O | X |
| 멤버 역할 변경 | O | O (member만) | X |
| 멤버 초대 | O | O | X |
| 멤버 제거 | O | O (member만) | X |
| 회의 생성 | O | O | O |
| 회의 참여 | O | O | O |
| PR 생성 | O | O | O |
| PR 리뷰 | O | O | O |
| PR merge | O | O | O* |

*member의 PR merge는 필수 approval 조건 충족 시에만 가능

---

## 회의 역할 (Meeting Roles)

### 역할 정의

| 역할 | 설명 |
|------|------|
| host | 회의 주최자 (회의 생성자) |
| participant | 회의 참여자 |

### 권한 매트릭스

| 작업 | host | participant |
|------|:----:|:-----------:|
| 회의 시작 | O | X |
| 회의 종료 | O | X |
| 회의 취소 | O | X |
| 회의 정보 수정 | O | X |
| 참여자 초대 | O | X |
| 참여자 강제 퇴장 | O | X |
| 회의 참여 | O | O |
| 발언 | O | O |
| 채팅 | O | O |
| Agent 호출 | O | O |
| Recording 다운로드 | O | O |
| Transcript 조회 | O | O |

---

## 메시지 가시성 (Message Visibility)

### 컨텍스트별 접근 범위

| 컨텍스트 | Public 음성 | Public 채팅 | Private 대화 | Tool 결과 |
|----------|:-----------:|:-----------:|:------------:|:---------:|
| 회의 참여 Agent | O | O | X | X |
| 개인 AI Assistant | O | O | O (본인만) | O (본인만) |
| 다른 참여자 | O | O | X | X |

### Public 메시지

- **정의**: 회의 참여자 전원에게 공개되는 메시지
- **범위**:
  - 회의 중 모든 음성 발화 (STT 결과)
  - 회의 채팅방의 일반 메시지
- **용도**: 회의 참여 Agent 컨텍스트, Transcript 생성

### Private 메시지

- **정의**: 특정 사용자와 AI assistant 간의 비공개 대화
- **범위**: 사용자가 assistant에게 직접 보낸 메시지 및 응답
- **용도**: 개인 질문, 메모, 개인 작업 요청
- **보안**: 다른 참여자 및 회의 참여 Agent에게 노출되지 않음

---

## PR 권한 (PR Permissions)

### PR 생성

- **권한**: Team member 이상
- **조건**: 없음 (누구나 PR 생성 가능)

### PR 리뷰

- **권한**: Team member 이상
- **조건**: PR 작성자 본인도 리뷰 가능 (approval은 불가)

### PR Approval

- **권한**: Team member 이상
- **조건**: PR 작성자 본인은 approval 불가
- **필요 수**: 팀 설정에 따름 (기본값: 1)

### PR Merge

- **권한**:
  1. 필수 approval 조건 충족 시: Team member 이상
  2. 또는: host / admin / owner
- **조건**: CON-001 (PR 승인 조건) 충족

### PR Close

- **권한**: PR 작성자 / host / admin / owner

---

## 데이터 접근 정책

### GT (Ground Truth)

- **조회**: Team member 이상
- **수정**: PR merge를 통해서만 (INV-003)

### Transcript

- **조회**: 해당 회의 참여자 또는 Team member 이상
- **수정**: 불가 (immutable)

### Recording

- **조회/다운로드**: 해당 회의 참여자 또는 Team member 이상
- **삭제**: admin / owner (보존 정책에 따름)

### Decision History (mit_blame)

- **조회**: Team member 이상
- **범위**: 해당 팀의 모든 결정 이력

---

## 감사 로그 접근

### 감사 로그 조회

- **권한**: admin / owner
- **범위**: 해당 팀의 모든 감사 로그

### 감사 로그 내보내기

- **권한**: owner
- **형식**: JSON / CSV

---

## API 인증

### 인증 방식

- JWT 기반 인증
- OAuth 2.0 지원 (Google, GitHub)

### 토큰 정책

| 항목 | 값 |
|------|-----|
| Access Token 만료 | 1시간 |
| Refresh Token 만료 | 7일 |
| LiveKit Token 만료 | 24시간 |

---

## 참조

- 비즈니스 규칙: [policy/01-business-rules.md](01-business-rules.md)
- 도메인 규칙: [domain/03-domain-rules.md](../domain/03-domain-rules.md)
