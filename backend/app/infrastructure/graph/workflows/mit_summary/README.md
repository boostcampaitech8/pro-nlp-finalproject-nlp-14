# MIT Summary 서브그래프

> **상태**: Scaffolding 완료 (구현 필요)
> **버전**: v1.0-alpha
> **최종 업데이트**: 2026-01-23

---

## 개요

`mit_summary`는 회의 실시간 부분 요약 및 GT(Ground Truth) 모순 감지 기능을 제공하는 LangGraph 서브그래프입니다.

### 주요 기능

1. **OrchestrationState 통합**: 이미 필터링된 messages 활용
2. **GT 모순 감지**: Knowledge Graph의 latest Decision과 비교하여 모순 탐지
3. **구조화된 요약**: 하이퍼클로바X 기반 전체/핵심/토픽별 요약 생성
4. **경량화 설계**: DB/Redis 직접 조회 없이 Orchestration이 제공한 데이터 활용

---

## 디렉토리 구조

```
backend/app/infrastructure/graph/
├── schema/
│   ├── __init__.py
│   └── models.py              # 공통 Pydantic 모델
│
└── workflows/
    └── mit_summary/
        ├── __init__.py         # 외부 export
        ├── state.py            # MitSummaryState 정의
        ├── connect.py          # 노드 연결 (내부용)
        ├── graph.py            # 컴파일된 그래프 (외부 API)
        └── nodes/
            ├── __init__.py
            ├── retrieval.py    # extract_utterances_from_messages, retrieve_gt_decisions
            ├── validation.py   # detect_contradictions
            └── summarization.py # generate_summary
```

---

## State 필드

### MitSummaryState (OrchestrationState 상속)

#### 상속된 필드 (OrchestrationState)

| 필드 | 타입 | 설명 |
|------|------|------|
| `run_id` | str | 실행 ID (trace 추적용) |
| `executed_at` | datetime | 실행 시각 |
| `messages` | List[BaseMessage] | 대화 메시지 목록 |
| `user_id` | str | 요청 사용자 ID |
| `plan` | str | 현재 실행 계획 |
| `need_tools` | bool | 도구 사용 필요 여부 |
| `tool_results` | str | 도구 실행 결과 (누적) |
| `retry_count` | int | 재시도 횟수 |
| `evaluation` | str | 평가 결과 |
| `evaluation_status` | str | 평가 상태 |
| `evaluation_reason` | str | 평가 사유 |
| `response` | str | 최종 응답 |

#### MIT Summary 전용 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `team_id` | UUID | 팀 ID (회의 소속 팀) |
| `mit_summary_meeting_id` | UUID | 회의 ID (메타데이터 참조용) |
| `mit_summary_query` | str | 사용자 요청 원문 |
| `mit_summary_utterances_raw` | list[Utterance] | messages에서 추출한 발화 |
| `mit_summary_gt_decisions` | list[GTDecision] | GT의 latest Decision 목록 |
| `mit_summary_contradictions` | list[Contradiction] | 감지된 모순 |
| `mit_summary_result` | SummaryOutput | 구조화된 요약 결과 |
| `mit_summary_text` | str | 최종 자연어 요약 |
| `mit_summary_metadata` | dict | 메타데이터 (duration 등) |
| `mit_summary_errors` | dict | 에러 기록 (노드별) |

**참고**: 
- `mit_summary_filter_params` 제거됨 (Orchestration에서 필터링 완료)
- `mit_summary_utterances_filtered` 제거됨 (이미 필터링된 messages 사용)

**필터 파라미터 예시**:
```python
# Orchestration 단계에서 이미 필터링된 messages가 전달됨
# mit_summary에서는 별도 필터링 불필요
```

---

## 그래프 흐름

```
START
  ↓
extract_utterances_from_messages (messages에서 발화 추출)
  ↓
retrieve_gt_decisions (GT에서 latest Decision 조회)
  ↓
detect_contradictions (모순 감지)
  ↓
generate_summary (LLM 요약 생성)
  ↓
END
```

**설계 원칙**:
- Orchestration에서 이미 필터링된 messages 전달받음
- 서브그래프는 변환 + 분석 + 생성만 담당
- DB/Redis 직접 조회 없음 (Orchestration 책임)

---

## 노드 설명

### 1. extract_utterances_from_messages
- **역할**: OrchestrationState의 messages에서 발화 추출
- **입력**: `messages` (이미 필터링됨)
- **출력**: `mit_summary_utterances_raw`
- **TODO**: messages 형식에 맞는 파싱 로직 구현

### 2. retrieve_gt_decisions
- **역할**: GT(Knowledge Graph)에서 latest Decision 조회
- **입력**: `team_id`
- **출력**: `mit_summary_gt_decisions`
- **TODO**: Knowledge Graph 연동 구현

### 3. detect_contradictions
- **역할**: 발화와 GT 비교하여 모순 감지
- **전략**: Semantic similarity + LLM 판단
- **출력**: `mit_summary_contradictions`
- **TODO**: Embedding + LLM 구현

### 4. generate_summary
- **역할**: 하이퍼클로바X로 구조화된 요약 생성
- **출력**: `mit_summary_result`, `mit_summary_text`
- **TODO**: 하이퍼클로바X 연동 구현
- **역할**: GT(Knowledge Graph)에서 latest Decision 조회
- **입력**: `team_id`, `filter_params` (topic)
- **출력**: `mit_summary_gt_decisions`
- **TODO**: Knowledge Graph 연동 구현 필요

### 4. detect_contradictions
- **역할**: 발화와 GT 비교하여 모순 감지
- **전략**: Semantic similarity + LLM 판단
- **출력**: `mit_summary_contradictions`
- **TODO**: Embedding + LLM 구현 필요

### 5. generate_summary
- **역할**: 하이퍼클로바X로 구조화된 요약 생성
- **출력**: `mit_summary_result`, `mit_summary_text`
- **TODO**: 하이퍼클로바X 연동 구현 필요

---

## 사용 예시

### 독립 실행

```python
from app.infrastructure.graph.workflows.mit_summary import get_mit_summary_graph

graph = get_mit_summary_graph()

result = await graph.ainvoke({
    "messages": [...],  # Orchestration에서 이미 필터링된 messages
    "team_id": team_id
})

print(result["mit_summary_text"])
```

### Orchestration 통합 (향후)

```python
from app.infrastructure.graph.workflows.orchestration import build_orchestration
from app.infrastructure.graph.workflows.mit_summary import get_mit_summary_graph

builder = build_orchestration()
builder.add_node("mit_summary", get_mit_summary_graph())
builder.add_conditional_edges("planner", route_intent, {
    "mit_summary": "mit_summary",
    "mit_search": "mit_search",
    ...
})
```

---

## 설계 결정 사항

### 1. State 필드 설계

**결정**: 자세한 중간 상태 필드 유지

**이유**:
- 디버깅 및 트레이싱 용이성
- 각 단계별 데이터 검증 가능
- 향후 UI에서 중간 결과 표시 가능 (예: 필터링 전후 비교)

### 2. 요약 결과 구조

**결정**: `SummaryOutput` Pydantic 모델 사용

**구조**:
```python
class SummaryOutput(BaseModel):
    overall: str                          # 전체 요약
    key_points: list[str]                 # 핵심 포인트
    topics: list[dict[str, str]]          # 토픽별 요약
    decisions_mentioned: list[str]        # 언급된 결정사항
    contradictions: list[Contradiction]   # 감지된 모순
    summary_metadata: dict                # 메타데이터
```

**이유**:
- 구조화된 데이터로 UI에서 다양하게 활용 가능
- 전체 요약 외 핵심 포인트만 빠르게 확인 가능
- 토픽별 요약으로 긴 회의도 구조적으로 파악
- 모순 정보를 명시적으로 제공하여 경고 표시

### 3. 필터링 전략

**결정**: State 기반 동적 필터링

**지원 필터**:
- `scope`: "recent_10min", "recent_30min", "full"
- `time_range`: 커스텀 시간 범위
- `speaker`: 화자 필터링
- `topic`: 키워드 검색

**이유**:
- 사용자 쿼리에 따라 유연하게 대응
- Orchestration에서 planning 단계가 filter_params 추출
- Summary 그래프는 파라미터만 받아 처리 (단일 책임)

### 4. 에러 처리 전략

**결정**: 에러 발생 시 기록하고 계속 진행

**이유**:
- 일부 노드 실패해도 최대한 요약 생성 시도
- 예: GT 조회 실패해도 기본 요약은 생성
- 에러 정보는 `mit_summary_errors` 필드에 기록
- 최종 응답에 에러 컨텍스트 포함 가능

### 6️⃣ **자연어 응답 형식**

**결정**: 마크다운 형식 사용

**이유**:
- UI에서 렌더링하기 좋음
- 계층 구조 (## 섹션) 명확
- 모순 경고에 이모지 사용으로 시각적 강조
- TTS 변환 시에도 섹션 구분 가능

---

## TODO 및 구현 우선순위

### Phase 1: 핵심 기능 (필수)
- [ ] **extract_utterances_from_messages**: messages 파싱 로직 구현
- [ ] **generate_summary**: 하이퍼클로바X LLM 연동
- [ ] **config.py**: 하이퍼클로바X API 키 설정 추가
- [ ] **utils/llm_factory.py**: `get_summary_llm()` 구현

### Phase 2: 고급 기능
- [ ] **retrieve_gt_decisions**: Knowledge Graph 연동
- [ ] **detect_contradictions**: Semantic similarity + LLM 판단

### Phase 3: 통합 및 테스트
- [x] **OrchestrationState 정의 및 상속** ✅ 완료
- [ ] Orchestration 그래프와 통합
- [ ] 단위 테스트 작성
- [ ] E2E 테스트 (실제 회의 데이터)

---

## 변경 이력

### 2026-01-23 (v2)
- ✅ **아키텍처 단순화**
  - 발화 조회/필터링 노드 제거 (Orchestration이 처리)
  - `extract_utterances_from_messages` 노드로 변환 단순화
  - `filtering.py` 파일 제거
  - State 필드 정리: `filter_params`, `utterances_filtered` 제거
  - 4단계 선형 파이프라인으로 간소화

### 2026-01-23 (v1)
- ✅ **OrchestrationState 통합 완료**
  - `workflows/orchestration/state.py` 생성
  - `MitSummaryState`가 `OrchestrationState` 상속
  - 중복 필드 제거 (messages, user_id 등)
  - `team_id` 필드만 추가 (Orchestration에 없는 필드)
- [ ] 단위 테스트 작성
- [ ] E2E 테스트 (실제 회의 데이터)

---

## 컨벤션 준수 체크리스트

- [x] **디렉토리명**: `mit_summary` (명사, snake_case)
- [x] **노드 함수명**: `retrieve_transcript`, `generate_summary` (동사 원형)
- [x] **State 클래스**: `MitSummaryState` (PascalCase, TypedDict)
- [x] **State prefix**: `mit_summary_` (디렉토리명과 동일)
- [x] **Pydantic 모델**: `schema/models.py` (공통 모델 중앙화)
- [x] **파일 구조**: `state.py`, `connect.py`, `graph.py`, `nodes/`
- [x] **Contract docstring**: reads/writes/side-effects/failures 명시
- [x] **반환 타입**: `MitSummaryState(field=value)` 형태
- [x] **로깅**: `logging.getLogger(__name__)` 사용
- [x] **타입 힌트**: 모든 함수/변수에 타입 명시

---

## 참고 문서

- [MitHub LangGraph Architecture](../../../../docs/agent/mithub-langgraph-architecture.md)
- [MitHub LangGraph Development Guideline](../../../../docs/agent/mithub-langgraph-development-guideline.md)
- [MitHub LangGraph Coding Convention](../../../../docs/agent/mithub-langgraph-coding-convention.md)
- [MIT 용어집](../../../../docs/spec/domain/01-glossary.md)
- [MIT 유즈케이스](../../../../docs/spec/usecase/01-usecase-specs.md)
