# MIT 유즈케이스 명세 (Use-case Specs)

## 범위

이 문서는 주요 유즈케이스의 목적, 입력, 출력, 성공/실패 조건 및 Acceptance Criteria를 정의한다.

---

## 회의 관련

### UC-001: 회의 생성

**개요**
- Actor: Team Member
- 목적: 새로운 회의 세션 생성

**Flow**
1. 사용자가 팀 선택 후 회의 생성 요청
2. 제목, 설명(선택), 예정 시각(선택) 입력
3. 시스템이 Meeting 레코드 생성 (status: scheduled)
4. 생성자가 자동으로 host 역할 부여

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| teamId | UUID | O | 팀 ID |
| title | string | O | 회의 제목 (1-255자) |
| description | string | X | 회의 설명 (0-2000자) |
| scheduledAt | datetime | X | 예정 시각 |

**출력**
- Meeting 객체 (id, title, status, createdAt 포함)

**예외**
| 코드 | 조건 |
|------|------|
| 401 | 인증되지 않음 |
| 403 | 해당 팀 멤버가 아님 |
| 400 | 유효하지 않은 입력 |

**Acceptance Criteria**
- [ ] 팀 멤버만 회의 생성 가능
- [ ] 생성자가 자동으로 host 지정
- [ ] 생성 시 status = scheduled
- [ ] 알림 발송 (팀원에게)

---

### UC-002: 회의 참여

**개요**
- Actor: Team Member
- 목적: 진행 중인 회의에 참여

**Flow**
1. 사용자가 회의 참여 요청
2. 시스템이 참여 권한 확인
3. LiveKit 토큰 발급
4. WebRTC 연결 수립
5. MeetingParticipant 레코드 생성
6. VAD 시작, 서버 녹음 시작

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| meetingId | UUID | O | 회의 ID |

**출력**
- LiveKit 토큰
- WebRTC 연결 정보

**예외**
| 코드 | 조건 |
|------|------|
| 401 | 인증되지 않음 |
| 403 | 참여 권한 없음 |
| 404 | 회의 없음 |
| 409 | 이미 참여 중 |

**Acceptance Criteria**
- [ ] 팀 멤버만 참여 가능
- [ ] 참여 시 MeetingParticipant 생성
- [ ] LiveKit 토큰 정상 발급
- [ ] 다른 참여자에게 입장 알림

---

### UC-003: 회의 시작

**개요**
- Actor: Host
- 목적: 예정된 회의를 시작

**Flow**
1. Host가 회의 시작 요청
2. 시스템이 권한 확인 (host 여부)
3. Meeting 상태를 ongoing으로 변경
4. Branch 자동 생성 (GT 기준)
5. 녹음 시작

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| meetingId | UUID | O | 회의 ID |

**출력**
- 업데이트된 Meeting 객체

**예외**
| 코드 | 조건 |
|------|------|
| 403 | host가 아님 |
| 400 | 이미 시작됨 / 취소됨 |

**Acceptance Criteria**
- [ ] host만 시작 가능
- [ ] status: scheduled -> ongoing
- [ ] Branch 자동 생성
- [ ] 참여자에게 시작 알림

---

### UC-004: 회의 종료

**개요**
- Actor: Host
- 목적: 진행 중인 회의를 종료

**Flow**
1. Host가 회의 종료 요청
2. 시스템이 권한 확인
3. Meeting 상태를 completed로 변경
4. 녹음 종료
5. Agent가 Transcript 생성 트리거
6. Agent가 Minutes 초안 생성
7. Agent가 Agenda 추출 (semantic matching으로 기존 Agenda 식별)
8. Agent가 각 Agenda에 대한 Decision 생성
9. Agent가 PR 자동 생성 (DecisionReview 포함)

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| meetingId | UUID | O | 회의 ID |

**출력**
- 업데이트된 Meeting 객체
- 생성된 PR 정보
- 추출된 Agenda 및 Decision 목록

**예외**
| 코드 | 조건 |
|------|------|
| 403 | host가 아님 |
| 400 | 진행 중이 아님 |

**Acceptance Criteria**
- [ ] host만 종료 가능
- [ ] status: ongoing -> completed
- [ ] 녹음 파일 저장
- [ ] Transcript 생성 (비동기)
- [ ] Minutes 초안 생성 (비동기)
- [ ] Agenda 추출 및 식별 (semantic matching)
- [ ] 각 Agenda에 대한 Decision 생성
- [ ] PR 자동 생성 (DecisionReview 포함)

---

## Agent 관련

### UC-005: Mit Blame 조회

**개요**
- Actor: Team Member
- 목적: 특정 결정의 변경 이력 및 맥락 조회

**Flow**
1. 사용자가 Agent에게 질문 ("이 예산 왜 5천만원이야?")
2. Agent가 의도 분석 -> mit_blame 도구 선택
3. GT DB에서 관련 Decision 검색
4. 변경 이력, 맥락, 참여자, 관련 회의록 조회
5. 자연어 응답 생성

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| query | string | O | 자연어 질문 |

**출력**
- 변경 히스토리 목록
- 각 변경의 맥락/사유
- 제안자 및 합의 참여자
- 관련 회의록 링크

**예외**
| 코드 | 조건 |
|------|------|
| 404 | 관련 결정 없음 |

**Acceptance Criteria**
- [ ] 질문에서 대상 Decision 식별
- [ ] 시간순 변경 이력 반환
- [ ] 각 변경의 근거(transcript 링크) 포함
- [ ] 자연어로 응답

---

### UC-006: Mit Search 조회

**개요**
- Actor: Team Member
- 목적: GT DB에서 관련 정보 검색

**Flow**
1. 사용자가 Agent에게 검색 요청 ("프로젝트 X 관련 결정사항 찾아줘")
2. Agent가 의도 분석 -> mit_search 도구 선택
3. GT DB에서 관련 Decision 검색 (semantic search)
4. 검색 결과 정리 및 응답

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| query | string | O | 검색 쿼리 |
| limit | integer | X | 결과 수 제한 (기본: 10) |

**출력**
- 관련 Decision 목록
- 각 Decision의 요약
- 관련 회의록 링크

**Acceptance Criteria**
- [ ] Semantic search 지원
- [ ] 관련도 순 정렬
- [ ] 결정 상태 표시 (latest/outdated)

---

### UC-007: Mit Branch 생성

**개요**
- Actor: Team Member
- 목적: 기존 GT에 이의 제기, 새 브랜치 생성

**Flow**
1. 사용자가 Agent에게 변경 제안 ("예산 6천만원으로 변경 제안")
2. Agent가 의도 분석 -> mit_branch 도구 선택
3. 새 Branch 생성 (base: 현재 GT)
4. 제안 내용 저장
5. 팀원에게 리뷰 요청 알림

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| target | string | O | 변경 대상 |
| proposed | string | O | 제안 내용 |
| context | string | X | 변경 사유 |

**출력**
- 생성된 Branch 정보
- 현재 GT 값 vs 제안 값 비교

**Acceptance Criteria**
- [ ] Branch 생성
- [ ] 제안 내용 저장
- [ ] 팀원 알림 발송

---

### UC-008: Mit Merge 실행 (Decision Approve)

**개요**
- Actor: Team Member (approval 조건 충족 시)
- 목적: 특정 Decision을 GT로 확정

**Flow**
1. 사용자가 Agent에게 merge 요청 ("이 결정 확정해줘")
2. Agent가 의도 분석 -> mit_merge 도구 선택
3. 해당 Decision의 DecisionReview 승인 상태 확인
4. Decision approve -> Decision 상태 latest로 변경
5. GT 업데이트 (해당 Decision만)
6. 모든 Decision 처리 시 PR 자동 close
7. 팀원에게 알림

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| decisionId | UUID | O | Decision ID |
| prId | UUID | O | PR ID |

**출력**
- 업데이트된 GT 정보 (해당 Decision)
- Decision 상태 변경 이력

**예외**
| 코드 | 조건 |
|------|------|
| 409 | 승인 조건 미충족 |
| 403 | 권한 없음 (본인 Decision approve 불가) |

**Acceptance Criteria**
- [ ] 승인 조건 검증
- [ ] 본인 Decision approve 불가 검증
- [ ] Decision 상태 -> latest
- [ ] GT 업데이트 (Decision 단위)
- [ ] 모든 Decision 처리 시 PR 자동 close
- [ ] 팀원 알림

---

## PR 관련

### UC-009: PR 코멘트 작성

**개요**
- Actor: Team Member
- 목적: PR의 특정 부분에 의견 추가

**Flow**
1. 사용자가 PR의 특정 위치에 코멘트 작성
2. 시스템이 코멘트 저장
3. PR 작성자 및 리뷰어에게 알림

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| prId | UUID | O | PR ID |
| content | string | O | 코멘트 내용 |
| position | object | X | 위치 정보 (decision_id, line 등) |

**출력**
- 생성된 Comment 객체

**Acceptance Criteria**
- [ ] 코멘트 저장
- [ ] 알림 발송
- [ ] 위치 정보 연결

---

### UC-010: PR Approval

**개요**
- Actor: Team Member (작성자 제외)
- 목적: PR 승인

**Flow**
1. 리뷰어가 PR 승인 요청
2. 시스템이 권한 확인 (작성자 != 리뷰어)
3. Approval 기록
4. 필수 approval 조건 확인
5. 조건 충족 시 merge 가능 상태로 변경

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| prId | UUID | O | PR ID |

**출력**
- 업데이트된 PR 객체

**예외**
| 코드 | 조건 |
|------|------|
| 403 | 본인 PR 승인 불가 |

**Acceptance Criteria**
- [ ] 작성자 본인 승인 불가
- [ ] Approval 기록
- [ ] 필수 조건 달성 시 알림

---

## Decision 관련

### UC-011: Decision Approve

**개요**
- Actor: 지정된 리뷰어 (Decision 작성자 제외)
- 목적: 특정 Decision을 GT에 반영

**Flow**
1. 지정된 리뷰어가 Decision approve 요청
2. 시스템이 권한 확인 (지정된 리뷰어 여부, Decision 작성자 != 리뷰어)
3. DecisionReview에 해당 리뷰어의 approval 기록
4. 지정된 리뷰어 전원 approve 여부 확인
5. 전원 approve 시 Decision 상태를 latest로 변경
6. GT 업데이트 (해당 Decision만)
7. 모든 Decision 처리 시 PR 자동 close

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| prId | UUID | O | PR ID |
| decisionId | UUID | O | Decision ID |

**출력**
- 업데이트된 DecisionReview 객체
- Decision 상태 변경 (전원 approve 시)

**예외**
| 코드 | 조건 |
|------|------|
| 403 | 지정된 리뷰어가 아님 |
| 403 | 본인 Decision approve 불가 |

**Acceptance Criteria**
- [ ] 지정된 리뷰어만 approve 가능
- [ ] Decision 작성자 본인 approve 불가
- [ ] DecisionReview에 리뷰어별 approval 기록
- [ ] 전원 approve 시 Decision -> latest
- [ ] GT 업데이트 (Decision 단위)
- [ ] 모든 Decision 처리 시 PR 자동 close

---

### UC-012: Decision Reject

**개요**
- Actor: 지정된 리뷰어
- 목적: 특정 Decision을 거부

**Flow**
1. 지정된 리뷰어가 Decision reject 요청
2. 시스템이 권한 확인 (지정된 리뷰어 여부)
3. DecisionReview 상태를 즉시 rejected로 변경
4. Decision 상태를 rejected로 변경
5. 다른 리뷰어의 approve 무효화
6. 모든 Decision 처리 시 PR 자동 close
7. 팀원에게 알림 (거부 사유 포함)

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| prId | UUID | O | PR ID |
| decisionId | UUID | O | Decision ID |
| reason | string | X | 거부 사유 |

**출력**
- 업데이트된 DecisionReview 객체
- Decision 상태 변경 (rejected)

**예외**
| 코드 | 조건 |
|------|------|
| 403 | 지정된 리뷰어가 아님 |

**Acceptance Criteria**
- [ ] 지정된 리뷰어만 reject 가능
- [ ] 1명이라도 reject하면 즉시 Decision rejected
- [ ] Decision 상태 -> rejected
- [ ] 다른 리뷰어의 approve 무효화
- [ ] 모든 Decision 처리 시 PR 자동 close
- [ ] 거부 알림 발송 (사유 포함)

---

### UC-013: Suggestion 수락

**개요**
- Actor: Decision 작성자 또는 Host
- 목적: Suggestion을 수락하여 Decision 수정

**Flow**
1. Decision 작성자 또는 Host가 Suggestion 수락 요청
2. 새로운 Decision 생성 (기존 Decision의 수정본)
3. 기존 Decision 상태를 rejected로 변경
4. 새로운 Decision에 대한 DecisionReview 생성
5. 리뷰어에게 재검토 알림

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| suggestionId | UUID | O | Suggestion ID |

**출력**
- 새로 생성된 Decision 객체
- 새로 생성된 DecisionReview 객체

**Acceptance Criteria**
- [ ] 새로운 Decision 생성
- [ ] 기존 Decision 상태 -> rejected
- [ ] 새로운 DecisionReview 생성
- [ ] 재검토 알림 발송

---

## 참조

- 워크플로우: [usecase/02-workflow-spec.md](02-workflow-spec.md)
- 도메인 규칙: [domain/03-domain-rules.md](../domain/03-domain-rules.md)
- 비즈니스 규칙: [policy/01-business-rules.md](../policy/01-business-rules.md)
