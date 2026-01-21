# MIT 용어집 (Glossary)

## 범위

이 문서는 MIT 프로젝트에서 사용하는 모든 도메인 용어를 정의한다.

---

## 핵심 개념

### GT (Ground Truth)

- **정의**: 팀이 현재 합의한 최신 결정의 집합
- **비유**: Git의 main 브랜치
- **특성**: 유기적 관계(지식 그래프)로 구축, 단순 나열 아님
- **관계**: PR merge를 통해서만 업데이트됨

### 회의 (Meeting)

- **정의**: 팀원들이 참여하여 안건을 논의하는 세션
- **상태**: `scheduled` -> `ongoing` -> `completed` -> `in_review` -> `confirmed` / `cancelled`
- **관계**: 1 Meeting -> 1 Minutes, 1 Meeting -> 1 Branch

### 회의록 (Minutes)

- **정의**: 한 회의에서 합의된 결과와 결정 과정을 요약한 문서
- **생성 시점**: 회의 종료 후 Agent가 초안 생성
- **관계**: 1 Meeting : 1 Minutes
- **용도**: GT 업데이트의 단위

### Transcript (발화 기록)

- **정의**: 회의 중 발화의 원문 기록 (STT 결과)
- **용도**: 회의록과 결정의 근거 자료
- **특성**: wall-clock timestamp 기반 정렬

### 결정사항 (Decision)

- **정의**: 합의된 사실 또는 선택
- **상태 파생**: 엔티티 자체가 저장하지 않음, 회의록 merge 상태로 파생
  - **latest**: main(GT)에 반영된 결정
  - **draft**: Branch/PR에 존재하는 결정
  - **outdated**: 이후 결정에 의해 대체된 과거 결정

### Branch (브랜치)

- **정의**: 회의록을 작성/수정하기 위한 작업 공간
- **특성**: GT에서 파생, 회의당 1개 생성
- **생명주기**: 회의 시작 시 생성, PR merge 또는 취소 시 종료

### PR (Pull Request)

- **정의**: Branch의 회의록을 GT로 병합하기 위한 리뷰/합의 절차
- **생성 시점**: 회의 종료 후 Agent가 자동 생성
- **활동**: Comment, Suggestion, Review -> Approval -> Merge

### Draft

- **정의**: merge 전 Branch/PR에 존재하는 회의록 또는 결정 상태
- **특성**: 아직 GT에 반영되지 않은 임시 상태

### Outdated

- **정의**: 이후의 결정에 의해 대체된 과거 결정 상태
- **특성**: 히스토리로 보존, GT에서는 최신 결정만 표시

---

## Mit Agent

### Mit Agent

- **정의**: 회의에 직접 참여하여 모든 작업의 중심이 되는 AI 에이전트
- **역할**: 사용자 요청 분석, 도구 선택 및 실행, 자연어 응답 생성
- **입력**: 음성(STT) 또는 텍스트
- **출력**: 자연어 응답 또는 TTS

### Mit Tools

Mit Agent가 호출하는 내부 도구:

| Tool | 설명 | 예시 호출 |
|------|------|-----------|
| `mit_blame` | 특정 결정의 히스토리와 맥락 조회 | "예산이 왜 5천만원이야?" |
| `mit_search` | GT DB에서 관련 정보 검색 | "프로젝트 X 관련 결정사항 찾아줘" |
| `mit_branch` | 기존 GT에 이의 제기, 새 브랜치 생성 | "예산 변경 제안할게" |
| `mit_merge` | 합의된 내용을 GT로 확정 | "이 내용으로 확정해줘" |
| `mit_summary` | 현재까지 회의 내용 요약 | "지금까지 뭐 얘기했어?" |
| `mit_action` | Action Item 추출 및 정리 | "할 일 목록 정리해줘" |

### MCP Tools

Mit Agent가 MCP(Model Context Protocol)를 통해 호출하는 외부 도구:

| Tool | 설명 |
|------|------|
| `mcp_jira` | Jira 이슈 생성/조회/수정 |
| `mcp_notion` | Notion 페이지 생성/수정 |
| `mcp_slack` | Slack 메시지 전송 |
| `mcp_calendar` | 일정 조회/생성 |
| `mcp_drive` | 문서 저장/공유/검색 |

---

## 리뷰 관련

### Comment

- **정의**: PR에서 특정 부분에 대한 의견이나 질문
- **주체**: 팀원 또는 Agent

### Suggestion

- **정의**: PR에서 특정 내용에 대한 수정 제안
- **특성**: 수락 시 회의록에 반영

### Review

- **정의**: PR 전체에 대한 검토 의견
- **상태**: Approve, Request Changes, Comment

### Approval

- **정의**: PR을 GT에 merge해도 좋다는 승인
- **조건**: 지정된 리뷰어의 approval 필요

---

## 컨텍스트 관련

### Public 메시지

- **정의**: 회의 참여자 전원에게 공개되는 메시지 (음성/채팅)
- **용도**: 회의 참여 Agent의 컨텍스트로 사용

### Private 메시지

- **정의**: 특정 사용자와 AI assistant 간의 비공개 대화
- **용도**: 해당 사용자의 개인 assistant 컨텍스트로만 사용

### 세션 (Session)

- **정의**: AI와의 연속적인 대화 컨텍스트
- **특성**: 이전 메시지가 기억되는 단위

---

## 조직 구조

### Team

- **정의**: 조직 단위, 회의와 GT를 공유하는 구성원 그룹
- **속성**: name, description, members

### Team Member

- **정의**: 팀에 소속된 사용자
- **역할**: owner, admin, member

### Meeting Participant

- **정의**: 특정 회의에 참여하는 사용자
- **역할**: host, participant

---

## 기술 용어

### STT (Speech-to-Text)

- **정의**: 음성을 텍스트로 변환하는 기술
- **용도**: 실시간 transcript 생성

### TTS (Text-to-Speech)

- **정의**: 텍스트를 음성으로 변환하는 기술
- **용도**: Agent 응답의 음성 출력

### VAD (Voice Activity Detection)

- **정의**: 음성 활동 감지
- **용도**: 발화 시작/종료 감지, STT 트리거

### WebRTC

- **정의**: 실시간 통신 기술
- **용도**: 회의 음성/영상 전송

### LiveKit

- **정의**: SFU 기반 WebRTC 미디어 서버
- **용도**: 회의 참여자 간 미디어 라우팅, 서버 녹음
