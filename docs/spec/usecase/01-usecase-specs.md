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

### UC-014: Mit Summary (회의 요약)

**개요**
- Actor: Team Member
- 목적: 현재까지 회의 내용 실시간 요약

**Flow**
1. 사용자가 Agent에게 요약 요청 ("지금까지 뭐 얘기했어?")
2. Agent가 의도 분석 -> mit_summary 도구 선택
3. 현재 세션의 transcript 분석
4. 논의된 주제, 잠정 결정, 미결 이슈 정리
5. 자연어 응답 생성

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| sessionId | UUID | O | 현재 회의 세션 ID |
| scope | string | X | 요약 범위 (all/recent, 기본: all) |

**출력**
- 논의 주제 목록
- 잠정 결정 사항
- 미결 이슈/논쟁점
- 참여자별 주요 발언 요약

**Acceptance Criteria**
- [ ] 현재 세션 transcript 기반 요약
- [ ] 주제별 그룹핑
- [ ] 시간순 정렬 옵션
- [ ] 자연어 응답

---

### UC-015: Mit Action (Action Item 관리)

**개요**
- Actor: Team Member
- 목적: 회의 중 Action Item 추출 및 정리

**Flow**
1. 사용자가 Agent에게 Action Item 요청 ("할 일 목록 정리해줘")
2. Agent가 의도 분석 -> mit_action 도구 선택
3. transcript에서 Action Item 패턴 추출
4. 담당자, 기한, 내용 구조화
5. 목록 반환

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| sessionId | UUID | O | 현재 회의 세션 ID |
| assignee | string | X | 특정 담당자 필터 |

**출력**
- Action Item 목록
- 각 Item: 내용, 담당자, 기한, 우선순위
- transcript 참조 링크

**예외**
| 코드 | 조건 |
|------|------|
| 404 | Action Item 없음 |

**Acceptance Criteria**
- [ ] transcript에서 Action Item 자동 추출
- [ ] 담당자 자동 식별 (발화자 기반)
- [ ] 기한 표현 파싱 ("다음 주까지", "금요일까지")
- [ ] 담당자별 필터링

---

## MCP Tools 관련

### UC-016: MCP Jira 연동

**개요**
- Actor: Team Member
- 목적: 회의 중 Jira 이슈 생성/조회/수정

**Flow**
1. 사용자가 Jira 관련 요청 ("이 버그 Jira에 등록해줘")
2. Agent가 의도 분석 -> mcp_jira 도구 선택
3. 필요한 정보 추출 (제목, 설명, 담당자 등)
4. Jira API 호출
5. 결과 응답

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| action | string | O | create/read/update |
| issueKey | string | X | 이슈 키 (read/update 시) |
| summary | string | X | 이슈 제목 (create 시) |
| description | string | X | 이슈 설명 |
| assignee | string | X | 담당자 |
| projectKey | string | X | 프로젝트 키 |

**출력**
- 생성된 이슈 키 및 링크
- 이슈 상세 정보
- 수정 결과

**Acceptance Criteria**
- [ ] Jira 이슈 생성
- [ ] 이슈 조회 (키 또는 검색)
- [ ] 이슈 상태/담당자 수정
- [ ] 링크 반환

---

### UC-017: MCP Notion 연동

**개요**
- Actor: Team Member
- 목적: Notion 페이지 생성/수정

**Flow**
1. 사용자가 Notion 관련 요청 ("이 내용 Notion에 기록해줘")
2. Agent가 내용 정리 -> mcp_notion 도구 선택
3. 대상 페이지/데이터베이스 식별
4. Notion API 호출
5. 결과 응답

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| action | string | O | create/update/append |
| pageId | string | X | 페이지 ID (update/append 시) |
| parentId | string | X | 부모 페이지 ID (create 시) |
| title | string | X | 페이지 제목 |
| content | string | X | 내용 (Markdown) |

**출력**
- 생성/수정된 페이지 링크
- 페이지 ID

**Acceptance Criteria**
- [ ] 페이지 생성
- [ ] 기존 페이지에 내용 추가
- [ ] Markdown -> Notion 블록 변환
- [ ] 링크 반환

---

### UC-018: MCP Slack 연동

**개요**
- Actor: Team Member
- 목적: Slack 메시지 전송

**Flow**
1. 사용자가 Slack 전송 요청 ("이 결정 #general에 공유해")
2. Agent가 메시지 작성 -> mcp_slack 도구 선택
3. 대상 채널/사용자 식별
4. Slack API 호출
5. 전송 확인

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| channel | string | O | 채널명 또는 사용자 ID |
| message | string | O | 메시지 내용 |
| threadTs | string | X | 스레드 타임스탬프 (답글 시) |

**출력**
- 전송 완료 확인
- 메시지 링크

**Acceptance Criteria**
- [ ] 채널 메시지 전송
- [ ] DM 전송
- [ ] 스레드 답글
- [ ] 메시지 포맷팅 (Markdown)

---

### UC-019: MCP Calendar 연동

**개요**
- Actor: Team Member
- 목적: 일정 조회/생성

**Flow**
1. 사용자가 캘린더 요청 ("다음 주 팀 일정 뭐 있어?")
2. Agent가 mcp_calendar 도구 선택
3. 날짜 범위/조건 파싱
4. Calendar API 호출
5. 결과 응답

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| action | string | O | list/create |
| startDate | datetime | X | 시작 날짜 |
| endDate | datetime | X | 종료 날짜 |
| title | string | X | 일정 제목 (create 시) |
| attendees | array | X | 참석자 목록 |

**출력**
- 일정 목록
- 생성된 일정 정보 및 링크

**Acceptance Criteria**
- [ ] 기간별 일정 조회
- [ ] 일정 생성 (참석자 포함)
- [ ] 자연어 날짜 파싱 ("다음 화요일")

---

### UC-020: MCP Drive 연동

**개요**
- Actor: Team Member
- 목적: 문서 저장/검색

**Flow**
1. 사용자가 Drive 요청 ("회의록 Drive에 저장해")
2. Agent가 mcp_drive 도구 선택
3. 대상 폴더/파일 식별
4. Drive API 호출
5. 결과 응답

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| action | string | O | upload/search/share |
| folderId | string | X | 대상 폴더 ID |
| fileName | string | X | 파일명 |
| content | string | X | 파일 내용 |
| query | string | X | 검색 쿼리 (search 시) |

**출력**
- 저장된 파일 링크
- 검색 결과 목록

**Acceptance Criteria**
- [ ] 파일 업로드
- [ ] 파일 검색
- [ ] 공유 링크 생성

---

## 복합 유즈케이스

### UC-C01: 회의 Agenda -> Jira 티켓 생성

**개요**
- Actor: Team Member
- 목적: 과거 회의의 특정 Agenda를 Jira 이슈로 생성

**Flow**
1. 사용자 요청 ("어제 회의에서 나온 결제 버그 아젠다 Jira 티켓으로 만들어줘")
2. Agent가 mit_search로 "어제 회의", "결제 버그" 관련 Agenda/Decision 검색
3. 해당 Agenda의 context, Decision 내용 추출
4. mcp_jira로 이슈 생성 (title, description, assignee 자동 매핑)
5. 생성된 티켓 링크 응답

**도구 조합**: mit_search -> mcp_jira

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| query | string | O | 자연어 요청 |

**출력**
- 검색된 Agenda 정보
- 생성된 Jira 이슈 키 및 링크

**Acceptance Criteria**
- [ ] 자연어에서 검색 조건 추출
- [ ] Agenda/Decision 내용을 Jira 필드에 매핑
- [ ] 담당자 자동 지정 (Decision 작성자 기반)

---

### UC-C02: Action Item -> Jira 일괄 등록

**개요**
- Actor: Team Member
- 목적: 회의에서 추출된 Action Item을 Jira 이슈로 일괄 생성

**Flow**
1. 사용자 요청 ("오늘 회의에서 나온 할 일 전부 Jira 티켓으로 등록해")
2. Agent가 mit_action으로 현재 회의의 Action Item 추출
3. 각 Item의 담당자, 내용, 기한 파악
4. mcp_jira로 각각 이슈 생성 (담당자 자동 지정)
5. 생성된 티켓 목록 응답

**도구 조합**: mit_action -> mcp_jira (batch)

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| sessionId | UUID | O | 회의 세션 ID |
| projectKey | string | X | Jira 프로젝트 키 |

**출력**
- 추출된 Action Item 목록
- 생성된 Jira 이슈 목록 (키, 링크)

**Acceptance Criteria**
- [ ] Action Item 자동 추출
- [ ] 일괄 이슈 생성
- [ ] 담당자/기한 자동 매핑
- [ ] 실패 시 부분 성공 결과 반환

---

### UC-C03: 과거 Decision -> Slack 공유

**개요**
- Actor: Team Member
- 목적: 과거 결정 사항을 Slack 채널에 공유

**Flow**
1. 사용자 요청 ("지난주 예산 결정 내용 #finance 채널에 공유해줘")
2. Agent가 mit_search로 "예산" 관련 최근 Decision 검색
3. 해당 Decision의 내용, 맥락, 승인 이력 추출
4. mcp_slack으로 채널에 포맷팅된 메시지 전송

**도구 조합**: mit_search -> mcp_slack

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| query | string | O | 자연어 요청 |

**출력**
- 검색된 Decision 정보
- Slack 메시지 전송 확인

**Acceptance Criteria**
- [ ] Decision 검색 및 추출
- [ ] 포맷팅된 메시지 생성 (제목, 내용, 승인자, 날짜)
- [ ] 채널/DM 전송

---

### UC-C04: 회의 요약 -> Notion 기록

**개요**
- Actor: Team Member
- 목적: 현재 회의 요약을 Notion 페이지에 기록

**Flow**
1. 사용자 요청 ("오늘 회의 내용 프로젝트 X Notion 페이지에 정리해줘")
2. Agent가 mit_summary로 현재 회의 요약 생성
3. 논의 주제, 결정 사항, Action Item 구조화
4. mcp_notion으로 해당 페이지에 추가

**도구 조합**: mit_summary -> mcp_notion

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| sessionId | UUID | O | 회의 세션 ID |
| pageId | string | O | Notion 페이지 ID 또는 이름 |

**출력**
- 생성된 요약 내용
- Notion 페이지 링크

**Acceptance Criteria**
- [ ] 회의 요약 자동 생성
- [ ] Notion 블록 구조로 변환
- [ ] 기존 페이지에 append 또는 새 페이지 생성

---

### UC-C05: Follow-up 미팅 생성 + 알림

**개요**
- Actor: Team Member
- 목적: 특정 Agenda에 대한 후속 미팅 생성 및 참석자 알림

**Flow**
1. 사용자 요청 ("이 아젠다 follow-up 미팅 다음주 화요일에 잡고 관련자들한테 알려줘")
2. Agent가 현재 Agenda의 참여자/이해관계자 파악
3. mcp_calendar로 미팅 일정 생성
4. mcp_slack으로 참석자들에게 알림

**도구 조합**: context -> mcp_calendar -> mcp_slack

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| agendaId | UUID | O | Agenda ID |
| dateExpression | string | O | 날짜 표현 ("다음주 화요일") |

**출력**
- 생성된 일정 정보
- 알림 전송 확인

**Acceptance Criteria**
- [ ] Agenda에서 관련자 추출
- [ ] 자연어 날짜 파싱
- [ ] 일정 생성 (참석자 자동 추가)
- [ ] Slack 알림 전송

---

### UC-C06: Decision 변경 이력 -> 문서화

**개요**
- Actor: Team Member
- 목적: 특정 Decision의 변경 히스토리를 문서로 저장

**Flow**
1. 사용자 요청 ("예산 결정 변경 히스토리 Drive에 문서로 저장해줘")
2. Agent가 mit_blame으로 해당 Decision의 전체 변경 이력 조회
3. 각 변경의 맥락, 사유, 참여자 정리
4. mcp_drive로 문서 생성 및 저장

**도구 조합**: mit_blame -> mcp_drive

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| query | string | O | 자연어 요청 |
| folderId | string | X | 저장 폴더 ID |

**출력**
- 변경 이력 문서 내용
- Drive 파일 링크

**Acceptance Criteria**
- [ ] 전체 변경 이력 조회
- [ ] 구조화된 문서 생성
- [ ] Drive 업로드

---

### UC-C07: 회의록 저장 + 팀 공유

**개요**
- Actor: Team Member
- 목적: 회의록을 Drive에 저장하고 팀 Slack에 공유

**Flow**
1. 사용자 요청 ("오늘 회의록 Drive에 저장하고 팀 Slack에 공유해")
2. Agent가 Minutes 내용 추출
3. mcp_drive로 문서 저장
4. mcp_slack으로 팀 채널에 링크 공유

**도구 조합**: internal -> mcp_drive -> mcp_slack

**입력**
| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| meetingId | UUID | O | 회의 ID |
| channel | string | O | Slack 채널명 |
| folderId | string | X | Drive 폴더 ID |

**출력**
- 저장된 파일 링크
- Slack 메시지 전송 확인

**Acceptance Criteria**
- [ ] Minutes 문서 생성
- [ ] Drive 업로드
- [ ] Slack 채널에 링크 공유
- [ ] 에러 시 부분 성공 처리

---

## 참조

- 워크플로우: [usecase/02-workflow-spec.md](02-workflow-spec.md)
- 도메인 규칙: [domain/03-domain-rules.md](../domain/03-domain-rules.md)
- 비즈니스 규칙: [policy/01-business-rules.md](../policy/01-business-rules.md)
- 도구 커버리지: [usecase/03-tools-coverage.md](03-tools-coverage.md)
