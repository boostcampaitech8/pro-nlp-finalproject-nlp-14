# MitHub Agent Overview

> 목적: MitHub 에이전트의 비전/역할/결정사항을 요약한다.
> 대상: 기획/개발/운영 전원.
> 범위: 고수준 개요와 결정 사항.
> 관련 문서: [MitHub LangGraph Architecture](./mithub-langgraph-architecture.md), [MitHub LangGraph Development Guideline](./mithub-langgraph-development-guideline.md), [MitHub LangGraph Coding Convention](./mithub-langgraph-coding-convention.md)

---

## 1. 핵심 컨셉 및 아키텍처

- **목표:** 단순 회의록 작성을 넘어, 회의의 맥락(Context)을 이해하고 의사결정의 정합성을 관리하는 에이전트 구축.

- **기술 스택:**
    - **Agent Framework:** LangGraph.
    - **Database:** 회의록 및 사내 문서 관리를 위한 Graph DB(지식 그래프) 구축 (메타데이터, PDF/HWP 지원).
    - **RAG:** 실시간 스크립트 기반 RAG 및 사내 문서 검색.

- **Tool 체계:**
    - **MCP Tools (외부 연동):** Jira, Notion, Slack, Calendar 등과 연동 (Model Context Protocol 활용).
    - **MIT Tools (자체 기능 - Git 컨셉 차용):**
        - mit_blame: 과거 결정 사항 추적 ("누가/언제 이렇게 정했지?").
        - mit_search: 내부 문서 및 회의록 검색.
        - mit_branch/merge: 회의 안건(토픽)을 브랜치처럼 분기하거나 합침.
        - mit_summary/action: 요약 및 액션 아이템 도출.

## 2. 에이전트의 역할 및 모드

- **음성 에이전트 (공용/회의 참가자):**
    - 회의 중 "박찬호(TMI)"가 되지 않도록 적절한 길이 조절 필요.
    - TTS뿐만 아니라 시각적 UI(마크다운, 이미지) 동반 출력.
    - **역할:** 실시간 요약, 팩트 체크, 문서 탐색, 외부 툴 제어(일정 등록 등).

- **챗봇 에이전트 (개인 비서):**
    - 개인적인 질문이나 검색(외부 지식/Web Search) 수행.
    - 감정적 케어(예: 상사의 반복적인 말에 대한 위로 등) 및 비공개 질의.

## 3. 타임라인별 주요 시나리오

| 구분 | 주요 기능 및 역할 |
|------|------------------|
| **회의 전** | - 이전 회의 GT(Ground Truth/확정 사항) 및 보류 안건 요약 알림.<br>- 회의 안건(Agenda) 자동 생성 및 소요 시간 예측.<br>- 지난 회의 정보 기반 장소/일정 리마인드. |
| **회의 중** | - **실시간 요약:** mit_summary로 논의 흐름 정리.<br>- **모순 감지:** 현재 발언이 과거 결정(GT)과 다를 경우 mit_blame을 통해 개입/경고.<br>- **토픽 감지:** 안건 전환 인식 및 관련 문서(예: 견적서) 자동 팝업.<br>- **브랜치 전략:** 보류 사항이나 별도 논의 필요 시 브랜치(Branch) 생성. |
| **회의 후** | - 회의록 PR(Pull Request) 생성 및 승인 요청.<br>- Action Item 감지 후 MCP 연동(티켓 생성 등).<br>- mit_recap을 통한 전체 요약 제공. |

## 4. 결정 사항

- **Agent Framework:** LangGraph 채택 (상세: [mithub-langgraph-architecture.md](./mithub-langgraph-architecture.md))
- **그래프 구조:** Orchestration(메인 그래프) + 기능별 서브그래프 방식 채택
- **서브그래프 통합:** Native Subgraph 방식 사용 (구체 구현은 Development Guideline 문서 참고)
- **State 관리:** OrchestrationState를 루트 State로, 서브그래프는 이를 상속/호환 (구체 스키마는 Development Guideline 문서 참고)
- **문서 관리:** 자체적으로 회의록 생산 및 관리

## 5. 미결정 사항

- **브랜치 전략:** 회의 중 브랜치 생성 권한 범위 (호스트 제한 여부)
- **Ground Truth 범위:** 회의록만 vs 사내 문서 전체 포함
- **Agent Call 방식:** 채팅 외 정형화된 폼(Form) 입력 필요성
