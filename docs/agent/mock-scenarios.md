# Mit Agent Mock 시연 시나리오

## 개요
Mit Agent Mock 시연을 위한 테스트 시나리오 문서입니다.

## 지원 명령어

| 명령어 | Tool | 응답 타입 | 설명 |
|--------|------|----------|------|
| "오늘 일정" | mit_search | direct | 오늘 예정된 회의 목록 조회 |
| "프로젝트 X 예산 왜 5천만원이야?" | mit_blame | direct | 예산 변경 히스토리 조회 |
| "팀 현황" | mit_search | direct | 팀 멤버 및 활동 현황 |
| "회의록 검색" | mit_search | form | 키워드/기간/팀 필터로 검색 |
| "예산 변경 제안" / "6천만원으로 올리자" | mit_branch | form | GT 변경 브랜치 생성 |
| "확정해줘" | mit_merge | direct | 브랜치 머지 (컨텍스트 필요) |
| "새 회의" / "회의 시작" | mit_action | modal | 회의 생성 모달 |
| "이번 주 Action Item" | mit_action | direct | Action Item 체크리스트 |
| "요약해줘" | mit_summary | direct | 현재 회의 요약 |

## 시나리오 1: 예산 변경 흐름 (blame -> branch -> merge)

### Step 1: blame 조회
- **입력**: "프로젝트 X 예산 왜 5천만원이야?"
- **Tool**: `mit_blame`
- **응답 타입**: direct
- **Right Panel**: 타임라인 뷰 (TimelineView)
  - 11/1: 3,000만원 (킥오프, 김OO 제안)
  - 11/15: 4,500만원 (범위 확대)
  - 11/22: +500만원 예비비 (불확실성 대비)
  - 12/30: 5,000만원 확정 (전원 합의)
- **컨텍스트 저장**: `{ target: "프로젝트 X 예산", currentValue: "5,000만원" }`

### Step 2: branch 생성
- **입력**: "6천만원으로 올리자"
- **Tool**: `mit_branch`
- **응답 타입**: form
- **폼 필드**:
  - 변경 금액 (pre-filled: 6,000만원)
  - 변경 사유 (필수)
  - 리뷰어 지정 (선택)
- **Right Panel**: BranchDiffView
  - 현재 GT: 5,000만원
  - 제안: 6,000만원
- **컨텍스트 업데이트**: `{ branchId: "branch-xxx", proposedValue: "6,000만원" }`

### Step 3: merge 확정
- **입력**: "확정해줘"
- **Tool**: `mit_merge`
- **응답 타입**: direct
- **조건**: branchId가 컨텍스트에 존재해야 함
- **Right Panel**: 타임라인 뷰 (새 항목 추가됨)
- **메시지**: "프로젝트 X 예산을 6,000만원으로 확정했습니다. 변경 이력이 기록되었습니다."
- **컨텍스트 클리어**: branchId 제거

## 시나리오 2: 회의록 검색

### Step 1: 검색 요청
- **입력**: "회의록 검색"
- **Tool**: `mit_search`
- **응답 타입**: form
- **폼 필드**:
  - 검색어 (필수)
  - 검색 기간 (최근 1주일/1개월/3개월/전체)
  - 팀 필터 (전체/개발팀/디자인팀/마케팅팀)

### Step 2: 검색 결과
- **폼 제출 후**
- **Right Panel**: 검색 결과 목록
- **히스토리**: 검색 성공 메시지

## 시나리오 3: 일정 조회 (Direct)

### Step 1: 일정 요청
- **입력**: "오늘 일정"
- **Tool**: `mit_search`
- **응답 타입**: direct
- **Right Panel**: 회의 카드 리스트
  - 주간 팀 미팅 (10:00-11:00, 회의실 A)
  - 프로젝트 리뷰 (14:00-15:30, 회의실 B)

## 시나리오 4: Action Item 조회

### Step 1: Action Item 요청
- **입력**: "이번 주 Action Item"
- **Tool**: `mit_action`
- **응답 타입**: direct
- **Right Panel**: ActionItemsView (체크리스트)
  - [ ] UI 디자인 검토 (김OO, 1/20)
  - [ ] API 스펙 정의 (이OO, 1/22)
  - [x] 예산 승인 요청 (박OO, 완료)

## 시나리오 5: 새 회의 생성 (Modal)

### Step 1: 회의 생성 요청
- **입력**: "새 회의" 또는 "회의 시작"
- **Tool**: `mit_action`
- **응답 타입**: modal
- **모달 내용**:
  - 회의 제목
  - 시작 시간
  - 참석자 선택
  - 의제 입력

## 응답 타입별 UI 동작

### Direct
1. 명령어 입력
2. 로딩 표시 (isProcessing: true)
3. 히스토리에 성공/실패 항목 추가
4. Right Panel 프리뷰 업데이트

### Form
1. 명령어 입력
2. InteractiveForm 표시 (Center Panel)
3. 사용자 입력
4. 폼 제출
5. 히스토리에 성공 항목 추가
6. Right Panel 프리뷰 업데이트

### Modal
1. 명령어 입력
2. 전용 모달 표시
3. 사용자 입력 및 제출
4. Left Panel 업데이트 (회의 카드 추가)

## 컨텍스트 동작

### 컨텍스트 저장 시점
- `mit_blame` 결과 반환 시 target, currentValue 저장
- `mit_branch` 폼 제출 시 branchId, proposedValue 저장

### 컨텍스트 참조 시점
- "올리자", "변경" 등 명령 시 이전 target 참조
- "확정해줘" 명령 시 branchId 확인

### 컨텍스트 클리어 시점
- `mit_merge` 완료 시
- 새로운 주제 명령 시 (다른 프로젝트 언급 등)

## 한계점 / 미지원 기능

### 미지원
- MCP 연동 (mcp_jira, mcp_slack, mcp_notion, mcp_calendar)
  - placeholder 응답만 제공
  - 실제 외부 서비스 연동 없음
- 실시간 STT/TTS 파이프라인
- 실제 Ground Truth DB 연동
- PR Review 워크플로우

### Mock 한계
- 모든 데이터는 하드코딩된 Mock
- 프로젝트 X 예산 시나리오만 완전 지원
- 다른 프로젝트/주제는 기본 응답 반환
