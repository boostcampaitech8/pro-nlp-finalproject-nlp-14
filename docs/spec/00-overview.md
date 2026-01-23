# Mit: 조직 지식 기반 AI 회의 시스템

## 요약

Git은 우리 팀의 코드의 Ground Truth이듯, Mit은 우리 팀의 Meeting Truth이다.

Mit은 회의록을 단순한 기록이 아닌 **팀이 합의한 검증된 사실(Ground Truth)의 저장소**로 만드는 시스템이다. Git의 PR Review처럼 팀원들이 회의 내용에 대해 Comment를 달고, Suggestion을 제안하며, **Decision별로 approve/reject**를 진행한다. 최종적으로 approved된 Decision만이 조직의 GT(Ground Truth)가 된다.

**Mit Agent**가 회의에 직접 참여하여 모든 작업의 중심이 된다. 사용자는 음성 또는 텍스트로 에이전트에게 요청하면, 에이전트가 적절한 도구(blame, merge, MCP 등)를 호출하여 처리한다. 이 과정이 반복되면서 팀의 지식 DB가 지속적으로 확장되고 정제된다.

## 슬로건

**모든 회의가 자산이 되는 순간**

---

## 핵심 개념

### GT (Ground Truth)

- **정의**: 팀이 현재 합의한 최신 결정의 집합
- **비유**: Git의 main 브랜치
- **구조**: Knowledge graph로 구성, Decision의 latest 상태만 포함
- **단위**: Agenda + Decision(latest)
- **관계**: Decision approve를 통해서만 업데이트됨 (Agenda당 최대 1개의 latest Decision 유지)

### Ground

- **정의**: 팀의 모든 합의된 결정과 그 이력을 포함하는 지식 저장소
- **비유**: Git의 repository (전체 히스토리 포함)
- **구조**: Knowledge graph로 구성, 모든 Decision 이력 포함
- **용도**: 과거 Decision 검색 (mit_blame, mit_search)
- **관계**: GT는 Ground의 현재 시점 스냅샷

### Agenda (안건)

- **정의**: 팀 전체에서 공유되는 논의 주제/안건
- **특성**: 여러 회의에 걸쳐 동일 Agenda가 재논의될 수 있음
- **식별**: AI semantic matching으로 기존 Agenda와 동일 여부 판단
- **제약**: Agenda당 최대 1개의 latest Decision만 유지
- **예시**: "프로젝트 X 예산", "출시 일정", "기술 스택 선정"

### Decision (결정사항)

- **정의**: 특정 회의에서 해당 Agenda에 대해 내린 결정
- **관계**: Agenda에 종속, 1 Agenda : N Decision
- **상태 파생**: DecisionReview 상태로 파생 (엔티티 자체가 저장하지 않음)
  - **draft**: PR에 존재하지만 아직 approved되지 않은 결정
  - **latest**: Decision이 approved되어 GT에 반영된 결정
  - **rejected**: 리뷰에서 거부된 결정 (합의 실패)
  - **outdated**: 이후 Decision에 의해 대체된 과거 결정 (합의 성공 후 갱신)

### Minutes (회의록)

- **정의**: 한 회의에서 논의된 안건과 결정 과정을 요약한 문서
- **생성 시점**: 회의 종료 후 Agent가 초안 생성
- **관계**: 1 Meeting : 1 Minutes, 1 Minutes : N Agenda
- **용도**: Agenda와 Decision 추출의 원천

### PR (Pull Request)

- **정의**: 회의의 Decision들을 GT로 병합하기 위한 리뷰/합의 절차
- **생성 시점**: 회의 종료 후 Agent가 자동 생성
- **활동**: Comment, Suggestion, Review -> **Decision별 Approve/Reject**
- **특성**: Decision별 부분 approve/reject 가능
- **종료 조건**: 모든 Decision이 처리(approved 또는 rejected)되면 자동 close

---

## Pain Point

| # | Pain Point | 현상 | 결과 |
|---|------------|------|------|
| 1 | **조직 지식의 휘발성** | 회의에서 합의한 내용이 체계적으로 축적되지 않음 | 같은 논의 반복, 조직 학습 불가 |
| 2 | **진실의 불확실성** | 예전 발화와 주제에 대해서 합의된 답이 없음 | 해석 충돌, 책임 회피 |
| 3 | **검증의 개인화** | 팩트체크가 개인의 작업으로 끝남 | 검증 결과 공유 안 됨, 중복 검증 |
| 4 | **맥락의 단절** | 회의마다 처음부터 다시 시작하는 느낌 | 비효율, 연속성 상실 |
| 5 | **합의 과정의 비가시성** | 회의 결론에 어떻게 도달했는지 추적 어려움 | 의사결정 품질 저하 |
| 6 | **실시간 확인 불가** | 회의 중 과거 결정 확인이 어려움 | 회의 중단, 시간 낭비 |

---

## 기존 접근과의 차별점

### 팩트체크 방향성 재정의

| 구분 | 기존 팩트체크 연구 | Mit의 접근 |
|------|-------------------|-----------|
| 검증 대상 | 통계, 수치, 정책 등 외부 사실 | 조직 내부 결정사항, 합의 내용 |
| 데이터 소스 | 뉴스, 논문, 공공 데이터 | Organization Ground (전체 이력) / GT (현재 상태) |
| 핵심 질문 | "이 통계가 사실인가?" | "우리가 이렇게 결정했나?" |

기존 ClaimBuster 등의 연구는 "시장 규모가 10조원이다"와 같은 통계적 주장의 진위를 외부 소스에서 검증한다. 그러나 조직 회의에서 실제로 필요한 것은 **"지난번에 예산을 얼마로 확정했지?"**, **"이 기능은 언제 출시하기로 했지?"**와 같은 내부 의사결정의 확인이다.

---

## Mit Agent 중심 아키텍처

### 핵심 개념

Mit의 모든 기능은 **Mit Agent**를 통해 실행된다. 사용자는 에이전트에게 자연어(음성/텍스트)로 요청하고, 에이전트가 적절한 도구를 선택하여 작업을 수행한다.

```
                        Mit Agent

   "모든 요청은 나를 통해"

   [사용자 요청]
        |
        v
   +----------------------------------------------------------+
   |              의도 분석 & 도구 선택                          |
   +----------------------------------------------------------+
        |
        +----------+----------+----------+---------
        v          v          v          v
   +--------+ +--------+ +--------+ +--------+
   | blame  | | merge  | | search |   MCP   |
   +--------+ +--------+ +--------+ +--------+
        |          |          |          |
        +----------+----------+----------+
                              |
                              v
                    +-------------------+
                    |      Ground       |
                    | (GT + 전체 이력)   |
                    +-------------------+
```

### Mit Agent Tools

에이전트가 호출할 수 있는 도구 목록:

| Tool | 설명 | 예시 호출 |
|------|------|----------|
| `mit_blame` | 특정 결정의 히스토리와 맥락 조회 | "예산이 왜 5천만원이야?" |
| `mit_search` | Ground에서 관련 정보 검색 | "프로젝트 X 관련 결정사항 찾아줘" |
| `mit_merge` | 특정 Decision을 GT로 확정 (Decision approve 트리거) | "이 결정 확정해줘" |
| `mit_summary` | 현재까지 회의 내용 요약 | "지금까지 뭐 얘기했어?" |
| `mit_action` | Action Item 추출 및 정리 | "할 일 목록 정리해줘" |
| `mcp_jira` | Jira 이슈 생성/조회/수정 | "이거 Jira 티켓으로 만들어줘" |
| `mcp_notion` | Notion 페이지 생성/수정 | "회의록 Notion에 올려줘" |
| `mcp_slack` | Slack 메시지 전송 | "팀 채널에 공유해줘" |
| `mcp_calendar` | 일정 조회/생성 | "다음 회의 언제야?" |

### 에이전트 동작 예시

**예시 1: blame 호출**
```
사용자: "프로젝트 X 예산이 왜 5천만원이야?"

Mit Agent 내부 처리:
  1. 의도 분석: 결정 히스토리 조회 요청
  2. 도구 선택: mit_blame
  3. 파라미터: { target: "프로젝트 X 예산" }
  4. Ground에서 해당 Agenda의 Decision 이력 조회
  5. 응답 생성

Mit Agent: "프로젝트 X 예산 변경 이력입니다.
           - 11월 1일: 3,000만원 (킥오프, 김OO 제안)
           - 11월 15일: 4,500만원 (범위 확대)
           - 11월 22일: +500만원 예비비 (불확실성 대비)
           - 12월 30일: 최종 5,000만원 확정 (전원 합의)"
```

**예시 2: MCP 연동**
```
사용자: "이 할 일들 Jira에 등록해줘"

Mit Agent 내부 처리:
  1. 의도 분석: Action Item을 Jira에 등록 요청
  2. 도구 선택: mit_action -> mcp_jira (체이닝)
  3. 실행:
     - mit_action으로 Action Item 추출
     - mcp_jira로 각 항목 티켓 생성

Mit Agent: "3개의 Jira 티켓을 생성했습니다.
           - MIT-123: UI 디자인 검토 (담당: 김OO, 기한: 1/20)
           - MIT-124: API 스펙 정의 (담당: 이OO, 기한: 1/22)
           - MIT-125: 예산 승인 요청 (담당: 박OO, 기한: 1/18)"
```

**예시 3: merge 흐름**
```
[회의 종료 후 PR 리뷰 진행]
[팀원 리뷰 - Decision별 approve/reject 진행]

사용자: "전원 동의했으니 확정해줘"

Mit Agent 내부 처리:
  1. 도구 선택: mit_merge
  2. DecisionReview 승인 상태 확인
  3. Decision approve -> GT 업데이트

Mit Agent: "프로젝트 X 예산을 6,000만원으로 확정했습니다.
           Decision 상태: draft -> latest
           변경 이력이 Ground에 기록되었습니다."
```

---

## 기능

### 1. Mit Agent (실시간 회의 지원)

Mit Agent가 회의에 직접 참여하여 실시간 STT를 수행하면서 모든 요청을 처리한다.

**파이프라인**
```
[음성 입력] -> STT -> Mit Agent -> Tool 실행 -> TTS -> [음성 출력]
```

**주요 역할**

1. **도구 오케스트레이션**
   - 사용자 요청을 분석하여 적절한 도구 선택
   - 복잡한 요청은 여러 도구를 체이닝하여 처리
   - 결과를 자연어로 변환하여 응답

2. **실시간 GT/Ground 조회 (blame, search)**
   - "이거 언제 결정했지?" -> `mit_blame` 호출
   - "왜 이렇게 됐지?" -> `mit_blame` 호출
   - "관련 내용 찾아줘" -> `mit_search` 호출

3. **외부 도구 연동 (MCP)**
   - "Jira에 등록해줘" -> `mcp_jira` 호출
   - "Slack에 공유해줘" -> `mcp_slack` 호출
   - "Notion에 정리해줘" -> `mcp_notion` 호출

4. **회의 진행 보조**
   - "요약해줘" -> `mit_summary` 호출
   - "할 일 정리해줘" -> `mit_action` 호출

---

### 2. 회의록 검토 (PR Review 스타일)

**해결하는 Pain Point**: 진실의 불확실성, 합의 과정의 비가시성

**작동방식**
1. 회의 종료 후 Mit Agent가 Minutes(회의록) 초안 생성
2. Agent가 Minutes에서 Agenda 추출 (semantic matching으로 기존 Agenda 식별)
3. 각 Agenda에 대한 Decision 생성
4. PR 자동 오픈 + DecisionReview 생성 (Decision별 리뷰어 자동 지정)
5. 팀원들이 Comment, Suggestion 추가
6. **Decision별로 approve/reject 진행**
   - approved: Decision 상태 -> latest, 즉시 GT 반영
   - rejected: Decision 상태 -> rejected
7. 모든 Decision 처리 완료 시 PR 자동 close
8. 변경 이력(Commit history) Ground에 영구 보존

---

### 3. 조직 지식 DB (GT / Ground)

**해결하는 Pain Point**: 조직 지식의 휘발성, 맥락의 단절

**GT (Ground Truth)**
- 팀이 현재 합의한 최신 결정의 집합
- 각 Agenda의 latest Decision만 포함
- 새 회의 시작 시 자동으로 관련 GT 로딩

**Ground**
- 팀의 모든 합의된 결정과 이력을 포함하는 저장소
- 모든 Decision 이력 포함 (latest, outdated, rejected)
- `mit_blame`, `mit_search` 도구로 실시간 조회

**가치**
- 이전 회의에서 나온 정보는 모두 검색 가능
- 조직 온보딩 시 빠른 학습 가능 (신입사원)
- 결정 변경의 맥락과 사유 추적 가능

---

### 4. mit blame (Tool: `mit_blame`)

**해결하는 Pain Point**: 합의 과정의 비가시성

Mit Agent의 핵심 도구. 특정 Agenda의 Decision 변경 히스토리와 맥락을 조회한다.

**호출 방식**
```
사용자: "이 예산이 5천만원인 이유가 뭐야?"
       "프로젝트 X 일정 변경 이력 보여줘"
       "이거 누가 결정한 거야?"

Mit Agent: mit_blame 도구 호출 -> Ground에서 히스토리 조회 -> 응답
```

**반환 정보**
- Decision 변경 히스토리 (언제, 무엇이, 어떻게 변경됐는지)
- 각 변경의 맥락/사유
- 제안자 및 합의 참여자 (리뷰어)
- 관련 회의록(Minutes) 링크
- Transcript 참조 (근거 발화)

---

### 5. mit merge (Tool: `mit_merge`)

**해결하는 Pain Point**: 검증의 개인화

PR 리뷰를 통해 Decision을 GT에 반영한다.

**작동방식**
```
1. 회의 종료 후 Agent가 PR 생성, DecisionReview 생성
2. 팀원들이 Discussion으로 검토 (Decision별로 approve/reject)
3. 합의 도달 시: "확정해줘" -> Mit Agent가 mit_merge 호출
   - DecisionReview 승인 조건 확인
   - Decision approve -> GT 업데이트
4. 합의 실패 시: Decision rejected
   - 새 회의에서 재제안 가능 (새로운 Decision으로 생성)
```

---

### 6. 회의 간 자동 연결

**해결하는 Pain Point**: 맥락의 단절

Mit Agent가 회의 내용을 분석하여 미결 사항이나 후속 조치가 필요한 부분을 자동 감지하고 제안한다.

**예시**
```
Mit Agent: "예산 증액에 합의했지만 구체적인 금액이 확정되지 않았습니다.
           새 Agenda로 생성하여 다음 회의에서 논의할까요?"

Mit Agent: "김OO님에게 UI 검토 업무가 할당되었습니다.
           mcp_jira로 티켓을 생성할까요?"
```

---

### 7. 외부 도구 연동 (MCP Tools)

Mit Agent가 MCP(Model Context Protocol)를 통해 외부 협업 도구와 연동한다.

**지원 도구**

| Tool | 기능 |
|------|------|
| `mcp_jira` | 이슈 생성, 상태 변경, 담당자 할당 |
| `mcp_notion` | 회의록 페이지 생성, 데이터베이스 업데이트 |
| `mcp_slack` | 채널 메시지 전송, 알림 발송 |
| `mcp_calendar` | 일정 조회, 회의 생성, 리마인더 설정 |
| `mcp_drive` | 문서 저장, 공유, 검색 |

**사용 예시**
```
사용자: "오늘 회의 내용 정리해서 팀 채널에 공유해줘"

Mit Agent 처리:
  1. mit_summary 호출 -> 회의 요약 생성
  2. mit_action 호출 -> Action Item 추출
  3. mcp_slack 호출 -> 팀 채널에 전송

Mit Agent: "팀 채널에 회의 요약과 Action Item을 공유했습니다."
```

---

## 서비스 파이프라인

### 실시간 회의

```
                     실시간 회의 파이프라인

  [참여자 음성]
       |
       v
  +---------+     +---------+     +------------------+
  |   STT   |---->|   VAD   |---->|  실시간 스크립트   |
  +---------+     +---------+     +--------+---------+
                                           |
         +----------------------------+----+----------+
         |                            |               |
         v                            v               v
  +---------------+          +---------------+  +----------+
  |  GT 참조      |          |   AI 헬퍼     |  |   화자   |
  |  자동 감지    |          |     봇        |  |   분리   |
  +---------------+          +-------+-------+  +----------+
                                     |
                                     v
                              +---------------+
                              |  음성 응답    |
                              |    (TTS)     |
                              +---------------+
```

### 회의 종료 후

```
1. 전체 스크립트 정제 (Offline STT + 화자 분리)
2. Minutes(회의록) 초안 생성 (LLM + GT 대조)
3. Agenda 추출 (semantic matching으로 기존 Agenda 식별)
4. 각 Agenda에 대한 Decision 생성
5. PR 자동 오픈 + DecisionReview 생성 (리뷰어 자동 지정)
6. Decision별 리뷰 프로세스 (팀원 검토 + 합의)
   - approved Decision -> 즉시 GT 반영
   - rejected Decision -> rejected 상태로 변경
7. 모든 Decision 처리 완료 시 PR 자동 close
8. Ground 업데이트 (전체 이력 기록)
9. Action Item 연동 (Jira, Notion, Slack - MCP)
```

---

## 시스템 아키텍처

```
                         Mit 아키텍처

  +------------------------------------------------------------+
  |                    회의 인터페이스                            |
  |  +----------+  +----------+  +----------+                  |
  |  | WebRTC   |  |   STT    |  |   TTS    |                  |
  |  | (음성)   |  |  엔진    |  |  엔진    |                  |
  |  +----------+  +----------+  +----------+                  |
  +------------------------------------------------------------+
                              |
                              v
  +------------------------------------------------------------+
  |                      Mit Agent                               |
  |                                                              |
  |   +----------------------------------------------------+    |
  |   |              의도 분석 & 도구 선택                    |    |
  |   +----------------------------------------------------+    |
  |                          |                                  |
  |   +----------------------+----------------------+           |
  |   |                      |                      |           |
  |   v                      v                      v           |
  |  +------------+  +------------+  +------------+            |
  |  | Mit Tools  |  | MCP Tools  |  | Util Tools |            |
  |  | - blame    |  | - jira     |  | - summary  |            |
  |  | - search   |  | - notion   |  | - action   |            |
  |  | - merge    |  | - slack    |  | - ...      |            |
  |  |            |  | - calendar |  |            |            |
  |  +------------+  +------------+  +------------+            |
  |                                                              |
  +------------------------------------------------------------+
                              |
                              v
  +------------------------------------------------------------+
  |                        Ground                                |
  |  +------------+  +------------+  +------------+             |
  |  |  Agenda    |  |  Decision  |  |  Minutes   |             |
  |  |  (안건)    |  |  (이력)    |  |  (회의록)  |             |
  |  +------------+  +------------+  +------------+             |
  |                                                              |
  |       GT = Ground의 현재 스냅샷 (latest Decision만)           |
  +------------------------------------------------------------+
```

### Tool 분류

| 분류 | Tools | 역할 |
|------|-------|------|
| **Mit Tools** | blame, search, merge | Ground/GT 조회 및 관리 |
| **MCP Tools** | jira, notion, slack, calendar, drive | 외부 서비스 연동 |
| **Util Tools** | summary, action | 회의 진행 보조 |

---

## 리뷰 프로세스

### Decision 상태 전이

```
[Decision 생성]
      |
      v
   +-------+
   | draft |  (PR에 존재, 아직 approved 안 됨)
   +---+---+
       |
       +---------------+
       |               |
       v               v
  +--------+      +----------+
  | latest |      | rejected |
  | (GT)   |      |          |
  +----+---+      +----------+
       |
       | (같은 Agenda의 새 Decision approved)
       v
  +----------+
  | outdated |
  +----------+
```

### DecisionReview 규칙

- **리뷰어 지정**: PR open 시 Agent가 각 Decision별로 자동 지정
- **추가 지정**: Host가 추가 리뷰어 지정 가능
- **승인 조건**: 지정된 리뷰어 **전원**의 approval 필요
- **거부 조건**: 리뷰어 **1명**이라도 reject하면 해당 Decision은 rejected
- **본인 제외**: Decision 작성자는 해당 Decision을 approve할 수 없음

---

## 핵심 가치

1. **조직 기억의 영속화**: 합의된 내용이 Ground에 영구 축적
2. **합의 기반 진실**: Decision별 approve를 통한 팀 합의만 GT로 인정
3. **점진적 지식 품질 향상**: 회의할수록 Ground가 정제되고 확장
4. **투명한 의사결정**: `mit_blame`을 통해 모든 Decision의 맥락 추적 가능
5. **에이전트 중심 통합**: 모든 작업을 Mit Agent 하나로 처리, 자연어로 요청

---

## Vision

### 단기
모든 회의가 조직의 지식 자산이 되는 세상

### 장기
AI가 조직의 Ground Truth를 기반으로 자율적으로 의사결정을 지원하는 시대

---

## 핵심 메시지

> **"Git이 코드의 Single Source of Truth를 만들듯,
> Mit은 조직 회의의 Single Source of Truth를 만든다.
>
> Mit Agent에게 말하면 된다.
> 과거 결정이 궁금하면 blame을, 확정이 필요하면 merge를,
> Jira 등록이 필요하면 그냥 말하면 된다.
>
> 모든 요청은 Mit Agent를 통해.
> 회의는 더 이상 휘발되지 않는다."**

---

## 참조

- 용어집: [domain/01-glossary.md](domain/01-glossary.md)
- 개념 모델: [domain/02-conceptual-model.md](domain/02-conceptual-model.md)
- 도메인 규칙: [domain/03-domain-rules.md](domain/03-domain-rules.md)
- 유즈케이스: [usecase/01-usecase-specs.md](usecase/01-usecase-specs.md)
- 워크플로우: [usecase/02-workflow-spec.md](usecase/02-workflow-spec.md)
