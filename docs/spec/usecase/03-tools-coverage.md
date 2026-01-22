# MIT Tools 유즈케이스 커버리지

## 범위

이 문서는 Mit Tools와 MCP Tools의 유즈케이스 정의 현황을 추적한다.
추후 유즈케이스 보완 작업 시 참조용.

---

## Mit Tools 커버리지

| Tool | 설명 | 유즈케이스 | 상태 |
|------|------|-----------|------|
| `mit_blame` | 특정 결정의 히스토리와 맥락 조회 | UC-005 | 정의됨 |
| `mit_search` | GT DB에서 관련 정보 검색 | UC-006 | 정의됨 |
| `mit_branch` | 기존 GT에 이의 제기, 새 브랜치 생성 | UC-007 | 정의됨 |
| `mit_merge` | 합의된 내용을 GT로 확정 | UC-008 | 정의됨 |
| `mit_summary` | 현재까지 회의 내용 요약 | - | 미정의 |
| `mit_action` | Action Item 추출 및 정리 | - | 미정의 |

### 미정의 Tools 상세

#### mit_summary

- **예시 호출**: "지금까지 뭐 얘기했어?"
- **필요한 유즈케이스**: 실시간 회의 요약 생성 및 조회

#### mit_action

- **예시 호출**: "할 일 목록 정리해줘"
- **필요한 유즈케이스**: Action Item 추출, 담당자 지정, 목록 조회

---

## MCP Tools 커버리지

| Tool | 설명 | 유즈케이스 | 상태 |
|------|------|-----------|------|
| `mcp_jira` | Jira 이슈 생성/조회/수정 | - | 미정의 |
| `mcp_notion` | Notion 페이지 생성/수정 | - | 미정의 |
| `mcp_slack` | Slack 메시지 전송 | - | 미정의 |
| `mcp_calendar` | 일정 조회/생성 | - | 미정의 |
| `mcp_drive` | 문서 저장/공유/검색 | - | 미정의 |

### 참고

MCP Tools는 외부 서비스 연동이므로 연동 우선순위에 따라 유즈케이스 정의 예정.

---

## 요약

| 카테고리 | 전체 | 정의됨 | 미정의 |
|----------|------|--------|--------|
| Mit Tools | 6 | 4 | 2 |
| MCP Tools | 5 | 0 | 5 |
| **합계** | **11** | **4** | **7** |

---

## 참조

- 용어집: [domain/01-glossary.md](../domain/01-glossary.md)
- 유즈케이스: [usecase/01-usecase-specs.md](01-usecase-specs.md)
