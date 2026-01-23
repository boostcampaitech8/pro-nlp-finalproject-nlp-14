# MIT Tools 유즈케이스 커버리지

## 범위

이 문서는 Mit Tools와 MCP Tools의 유즈케이스 정의 현황을 추적한다.

---

## Mit Tools 커버리지

| Tool | 설명 | 유즈케이스 | 상태 |
|------|------|-----------|------|
| `mit_blame` | 특정 결정의 히스토리와 맥락 조회 | UC-005 | 정의됨 |
| `mit_search` | GT DB에서 관련 정보 검색 | UC-006 | 정의됨 |
| `mit_branch` | 기존 GT에 이의 제기, 새 브랜치 생성 | UC-007 | 정의됨 |
| `mit_merge` | 합의된 내용을 GT로 확정 | UC-008 | 정의됨 |
| `mit_summary` | 현재까지 회의 내용 요약 | UC-014 | 정의됨 |
| `mit_action` | Action Item 추출 및 정리 | UC-015 | 정의됨 |

---

## MCP Tools 커버리지

| Tool | 설명 | 유즈케이스 | 상태 |
|------|------|-----------|------|
| `mcp_jira` | Jira 이슈 생성/조회/수정 | UC-016 | 정의됨 |
| `mcp_notion` | Notion 페이지 생성/수정 | UC-017 | 정의됨 |
| `mcp_slack` | Slack 메시지 전송 | UC-018 | 정의됨 |
| `mcp_calendar` | 일정 조회/생성 | UC-019 | 정의됨 |
| `mcp_drive` | 문서 저장/공유/검색 | UC-020 | 정의됨 |

---

## 복합 유즈케이스 커버리지

복합 유즈케이스는 여러 도구를 조합하여 사용하는 시나리오를 정의한다.

| 유즈케이스 | 설명 | 도구 조합 |
|------------|------|-----------|
| UC-C01 | 회의 Agenda -> Jira 티켓 생성 | mit_search -> mcp_jira |
| UC-C02 | Action Item -> Jira 일괄 등록 | mit_action -> mcp_jira |
| UC-C03 | 과거 Decision -> Slack 공유 | mit_search -> mcp_slack |
| UC-C04 | 회의 요약 -> Notion 기록 | mit_summary -> mcp_notion |
| UC-C05 | Follow-up 미팅 생성 + 알림 | context -> mcp_calendar -> mcp_slack |
| UC-C06 | Decision 변경 이력 -> 문서화 | mit_blame -> mcp_drive |
| UC-C07 | 회의록 저장 + 팀 공유 | internal -> mcp_drive -> mcp_slack |

---

## 요약

| 카테고리 | 전체 | 정의됨 | 미정의 |
|----------|------|--------|--------|
| Mit Tools | 6 | 6 | 0 |
| MCP Tools | 5 | 5 | 0 |
| 복합 유즈케이스 | 7 | 7 | 0 |
| **합계** | **18** | **18** | **0** |

---

## 참조

- 용어집: [domain/01-glossary.md](../domain/01-glossary.md)
- 유즈케이스: [usecase/01-usecase-specs.md](01-usecase-specs.md)
