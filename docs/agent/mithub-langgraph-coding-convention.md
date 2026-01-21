# MitHub LangGraph Coding Convention

버전: v2.0

> 목적: LangGraph 기반 그래프/노드 개발 시 코드 규칙을 통일한다.
> 대상: LangGraph 그래프/노드 구현자.
> 범위: 네이밍, 노드 구현 규칙, 로깅/타입/async 규칙.
> 비범위: 개발 절차, 아키텍처 결정.
> 관련 문서: [MitHub LangGraph Development Guideline](./mithub-langgraph-development-guideline.md), [MitHub LangGraph Architecture](./mithub-langgraph-architecture.md)

---

## 1. 의미론적 네이밍 규칙

### 1.1 노드 함수명 원칙

> **핵심**: 노드 함수명은 **동사 원형**으로 시작하여 수행하는 **행위**를 명확히 표현한다. (등록명은 2.2 규칙 적용)

| 원칙 | 설명 | 예시 |
|-----|------|-----|
| **동사 원형 시작** | 노드는 행위를 수행하므로 동사 원형으로 시작 | `retrieve_documents` (O), `retrieving_documents` (X) |
| **동명사(-ing) 금지** | 진행 상태가 아닌 실행 단위이므로 | `generate_answer` (O), `generating_answer` (X) |
| **명사 단독 금지** | 행위가 불분명해짐 | `route_intent` (O), `router` (X), `intent` (X) |
| **목적어 포함** | 무엇을 대상으로 하는지 명시 | `extract_action_items` (O), `extract` (X) |

### 1.2 동사 카테고리별 사용 가이드

| 카테고리 | 권장 동사 | 용도 | 예시 |
|---------|----------|------|-----|
| **데이터 획득** | `retrieve`, `fetch`, `load`, `get` | 외부 소스에서 데이터 가져오기 | `retrieve_documents`, `fetch_meeting_data` |
| **데이터 생성** | `generate`, `create`, `build`, `compose` | 새로운 데이터 생성 | `generate_answer`, `create_plan`, `build_context` |
| **데이터 변환** | `transform`, `convert`, `parse`, `format` | 형태 변환 | `transform_query`, `parse_user_input` |
| **데이터 추출** | `extract`, `filter`, `select` | 일부 추출 | `extract_action_items`, `filter_relevant_docs` |
| **분석/판단** | `analyze`, `evaluate`, `assess`, `classify` | 분석 후 결과 도출 | `analyze_intent`, `evaluate_response`, `classify_query` |
| **라우팅/결정** | `route`, `decide`, `determine`, `select` | 다음 경로 결정 | `route_intent`, `decide_next_step` |
| **검증** | `validate`, `verify`, `check` | 유효성 검사 | `validate_input`, `verify_context` |
| **병합/조합** | `merge`, `combine`, `aggregate`, `synthesize` | 여러 데이터 합치기 | `merge_contexts`, `synthesize_answer` |
| **저장/기록** | `save`, `store`, `record`, `persist` | 영구 저장 | `save_result`, `record_decision` |

### 1.3 금지 패턴

| 패턴 | 이유 | 잘못된 예시 | 올바른 예시 |
|-----|------|-----------|-----------|
| **동명사 (-ing)** | 상태가 아닌 행위 | `retrieving`, `generating` | `retrieve`, `generate` |
| **명사 단독** | 행위 불분명 | `retriever`, `generator`, `router` | `retrieve_docs`, `generate_answer`, `route_intent` |
| **과거형** | 완료 상태 혼동 | `retrieved`, `generated` | `retrieve`, `generate` |
| **be 동사** | 행위 불분명 | `is_valid`, `be_ready` | `validate_input`, `prepare_context` |
| **모호한 동사** | 목적 불분명 | `do_something`, `process_data`, `handle_request` | 구체적 동사 사용 |

### 1.4 노드 함수명 구조

```
<동사>_<목적어>(_<수식어>)?

예시:
- retrieve_documents
- generate_final_answer
- route_by_intent
- validate_user_input
- extract_action_items_from_transcript
```

### 1.5 특수 노드 함수 네이밍

| 노드 유형 | 네이밍 패턴 | 예시 |
|----------|-----------|-----|
| **라우터 노드** | `route_*`, `decide_*` | `route_intent`, `decide_next_action` |
| **검증 노드** | `validate_*`, `verify_*` | `validate_input`, `verify_permissions` |
| **폴백 노드** | `fallback_*`, `handle_*_error` | `fallback_generate`, `handle_retrieval_error` |

---

## 2. 서브그래프/워크플로우 네이밍

### 2.1 워크플로우 디렉토리명

> **원칙**: 명사 또는 명사구로 도메인/기능 표현

| 규칙 | 설명 | 예시 |
|-----|------|-----|
| **snake_case** | 디렉토리명 규칙 | `rag`, `mit_search`, `document_qa` |
| **명사/명사구** | 기능 도메인 표현 | `rag` (O), `retrieve_and_generate` (X) |
| **약어 허용** | 널리 알려진 경우 | `rag`, `qa`, `stt` |
| **동사 금지** | 행위가 아닌 도메인 | `mit_summary` (O), `summarize` (X) |

```
workflows/
├── orchestration/    # 오케스트레이션 (메인, 시스템명)
├── rag/              # RAG 서브그래프
├── mit_search/       # MIT 검색 서브그래프
├── mit_summary/      # 요약 서브그래프
└── action_extraction/# 액션 아이템 추출
```

### 2.2 그래프 등록명 (add_node)

> **원칙**: 행위자 노드는 역할 중심 명사로 등록하고, 시스템(서브그래프)은 디렉토리명(명사)을 그대로 사용

```python
# connect.py

# Good - 시스템(서브그래프)은 명사
builder.add_node("rag", rag_graph)
builder.add_node("mit_search", mit_search_graph)
builder.add_node("mit_summary", mit_summary_graph)

# Good - 행위자(노드)는 역할 중심 명사
builder.add_node("intent_router", route_intent)
builder.add_node("planner", create_plan)
builder.add_node("generator", generate_answer)

# Bad - 시스템을 행위자처럼 등록
builder.add_node("rager", rag_graph)  # X
builder.add_node("mit_searcher", mit_search_graph)  # X
```

---

## 3. State 필드 네이밍

### 3.1 기본 규칙

| 규칙 | 설명 | 예시 |
|-----|------|-----|
| **snake_case** | Python 표준 | `user_input`, `documents` |
| **명사/명사구** | 데이터 표현 | `documents`, `mit_search_results` |
| **서브그래프 prefix** | 충돌 방지 | `rag_documents`, `mit_search_query` |

### 3.2 prefix 규칙

> **원칙**: prefix는 **디렉토리명과 동일**하게 사용

```python
# OrchestrationState (루트) - prefix 없음
class OrchestrationState(TypedDict):
    messages: list           # 공통
    routing: RoutingDecision # 공통
    plan: PlanOutput         # 공통

# RagState (서브그래프) - rag_ prefix (디렉토리: rag/)
class RagState(OrchestrationState):
    rag_query: str           # RAG 전용
    rag_documents: list      # RAG 전용
    rag_context: str         # RAG 전용

# MitSearchState (서브그래프) - mit_search_ prefix (디렉토리: mit_search/)
class MitSearchState(OrchestrationState):
    mit_search_query: str        # MIT Search 전용
    mit_search_results: list     # MIT Search 전용
    mit_search_filters: dict     # MIT Search 전용
```

**prefix 결정 규칙**:
| 디렉토리명 | prefix | 예시 |
|-----------|--------|-----|
| `rag/` | `rag_` | `rag_documents` |
| `mit_search/` | `mit_search_` | `mit_search_results` |
| `mit_summary/` | `mit_summary_` | `mit_summary_text` |

### 3.3 상태 필드 의미 분류

| 접미사 | 의미 | 예시 |
|-------|------|-----|
| `*_query` | 검색/질의 입력 | `rag_query`, `mit_search_query` |
| `*_results` | 처리 결과 목록 | `mit_search_results`, `evaluation_results` |
| `*_documents` | 문서 목록 | `rag_documents`, `retrieved_documents` |
| `*_context` | 컨텍스트 문자열 | `rag_context`, `conversation_context` |
| `*_decision` | 결정 사항 | `routing_decision`, `final_decision` |
| `*_metadata` | 부가 정보 | `request_metadata`, `trace_metadata` |

---

## 4. 클래스/타입 네이밍

### 4.1 State 클래스

> **원칙**: State 클래스는 `total=False`로 정의하여 부분 반환(패치)을 타입 안전하게 지원한다.

```python
# State 정의 - total=False로 부분 반환 허용
class OrchestrationState(TypedDict, total=False):
    messages: list
    routing: RoutingDecision
    plan: PlanOutput

class RagState(OrchestrationState, total=False):
    rag_query: str
    rag_documents: list
```

**네이밍**: `<워크플로우명>State` (예: `OrchestrationState`, `RagState`, `MitSearchState`)

### 4.2 Pydantic 모델 (schema/models.py)

| 유형 | 패턴 | 예시 |
|-----|------|-----|
| **결정/결과** | `*Decision`, `*Result`, `*Output` | `RoutingDecision`, `PlanOutput` |
| **데이터 객체** | 도메인 명사 | `Document`, `Utterance`, `EvidenceRef` |
| **에러/기록** | `*Record`, `*Error` | `ErrorRecord`, `TraceRecord` |

```python
# schema/models.py

class RoutingDecision(BaseModel):   # 라우팅 결정
    next: str
    reason: str

class PlanOutput(BaseModel):        # 플래닝 출력
    steps: list[str]
    requires_rag: bool

class Document(BaseModel):          # 문서 객체
    id: str
    content: str
    score: float
    metadata: dict[str, Any]

class ErrorRecord(BaseModel):       # 에러 기록
    node: str
    error_type: str
    message: str
```

---

## 5. 파일명 규칙

### 5.1 노드 파일

> **원칙**: 노드 파일명은 **기능 명사** (동명사 형태)를 snake_case로 사용
> **원칙**: 노드 코드는 `nodes/` 디렉토리에만 둔다. 필요한 경우 `nodes/` 아래에 하위 모듈을 둔다.

```
workflows/<name>/nodes/
├── planning.py          # 플래닝 관련 노드들 (create_plan, refine_plan)
├── routing.py           # 라우팅 관련 노드들 (route_intent, decide_fallback)
├── answering.py         # 응답 생성 관련 노드들 (generate_answer)
└── retrieval.py         # 검색 관련 노드들 (retrieve_documents)
    ├── indexing/         # 하위 모듈 (예: 인덱싱)
    ├── pre_retrieval/    # 하위 모듈 (예: 전처리/쿼리 리라이트)
    └── retrieval/        # 하위 모듈 (예: 검색 단계 분리)
```

**규칙**:
- 파일명: **동명사/기능 명사** (`planning`, `routing`, `retrieval`)
- 위치: `nodes/` 하위에만 배치 (필요 시 `nodes/<submodule>/`로 분리)
- 함수명: **동사 원형 + 목적어** (`create_plan`, `route_intent`)
- 파일 하나에 관련 노드 함수들을 그룹핑

---

## 6. 네이밍 요약

| 대상 | 패턴 | 예시 |
|-----|------|-----|
| 노드 함수 | `<동사>_<목적어>` | `retrieve_documents` |
| 노드 등록명 | 역할 명사 | `planner`, `intent_router` |
| 서브그래프 등록명 | 디렉토리명 | `rag`, `mit_search` |
| State 클래스 | `<Name>State` | `OrchestrationState` |
| State prefix | `<subgraph>_` | `rag_`, `mit_search_` |
| 모델 클래스 | PascalCase | `RoutingDecision`, `PlanOutput` |

---

## 7. 노드 구현 규칙

| 규칙 | O | X |
|-----|---|---|
| 반환 타입 | `<StateType>(field=value)` | `{"field": value}` dict 리터럴 |
| 함수 형태 | `def node(state) -> <StateType>` | 클래스 |
| LLM 초기화 | `get_*_llm()` | 직접 생성 |
| 환경변수 | `config.py` 경유 | `os.getenv()` |
| 에러 처리 | `errors` 필드 기록 | raise |

### 7.1 State 반환 규칙

> **원칙**: 노드는 명시적으로 State 타입을 사용하여 반환한다. dict 리터럴 대신 `<StateType>(field=value)` 형태를 사용한다.

```python
# Good - 명시적 State 타입 사용
def route_intent(state: OrchestrationState) -> OrchestrationState:
    return OrchestrationState(routing=RoutingDecision(next="rag", reason="검색 필요"))

# Bad - dict 리터럴 (타입 안전성 미활용)
def route_intent(state: OrchestrationState) -> OrchestrationState:
    return {"routing" : RoutingDecision(next="rag", reason="검색 필요")}
```

**이점**:
- 필드명 오타 시 IDE/타입 체커가 즉시 감지
- 자동완성 지원
- 어떤 State를 반환하는지 코드에서 명확히 표현

---

## 8. 노드 계약(Contract) 규칙

### 8.1 필수 주석 형식

```python
def retrieve_documents(state: RagState) -> dict:
    """관련 문서를 벡터스토어에서 검색

    Contract:
        reads: rag_query, messages
        writes: rag_documents
        side-effects: VectorStore 조회
        failures: RETRIEVAL_FAILED -> errors 기록
    """
```

### 8.2 에러 코드 네이밍

> **원칙**: `UPPER_SNAKE_CASE`, `<행위>_<결과>` 형태

| 패턴 | 예시 |
|-----|-----|
| `*_FAILED` | `RETRIEVAL_FAILED`, `GENERATION_FAILED` |
| `*_EMPTY` | `CONTEXT_EMPTY`, `DOCUMENTS_EMPTY` |
| `*_INVALID` | `INPUT_INVALID`, `FORMAT_INVALID` |
| `*_TIMEOUT` | `LLM_TIMEOUT`, `API_TIMEOUT` |
| `*_NOT_FOUND` | `DOCUMENT_NOT_FOUND`, `MEETING_NOT_FOUND` |

---

## 9. 비동기 규칙

### 9.1 async vs sync 선택 기준

| 상황 | 선택 | 이유 |
|-----|------|-----|
| LLM 호출 포함 | `async def` | I/O 바운드 작업 |
| DB/API 호출 포함 | `async def` | I/O 바운드 작업 |
| 순수 계산/변환 | `def` | CPU 바운드 작업 |
| 외부 호출 없음 | `def` | 불필요한 오버헤드 방지 |

### 9.2 예시

```python
# 비동기 노드 (LLM 호출)
async def generate_answer(state: OrchestrationState) -> dict:
    """응답 생성 (비동기)

    Contract:
        reads: messages, rag_context
        writes: messages
        side-effects: LLM API 호출
    """
    llm = get_generator_llm()
    response = await llm.ainvoke(...)  # 비동기 호출
    return {"messages": [response]}


# 동기 노드 (순수 계산)
def route_intent(state: OrchestrationState) -> dict:
    """라우팅 결정 (동기)

    Contract:
        reads: messages
        writes: routing
        side-effects: none
    """
    # 단순 조건 분기, LLM 미사용
    return OrchestrationState(routing=RoutingDecision(...))
```

---

## 10. 로깅 규칙

### 10.1 로거 설정

```python
# 각 노드 파일 상단
import logging

logger = logging.getLogger(__name__)
```

### 10.2 로깅 레벨 가이드

| 레벨 | 용도 | 예시 |
|-----|------|-----|
| `DEBUG` | 상세 디버깅 정보 | 입력 state 내용, 중간 결과 |
| `INFO` | 주요 실행 흐름 | 노드 시작/종료, 분기 결정 |
| `WARNING` | 예상된 문제 | 폴백 실행, 빈 결과 |
| `ERROR` | 복구 가능한 에러 | API 실패 후 재시도 |
| `EXCEPTION` | 예상치 못한 에러 | 스택 트레이스 포함 |

### 10.3 예시

```python
def retrieve_documents(state: RagState) -> dict:
    query = state.get("rag_query")
    logger.info(f"문서 검색 시작: query={query[:50]}...")

    try:
        documents = _search(query)
        logger.info(f"검색 완료: {len(documents)}건")
        return {"rag_documents": documents}

    except ConnectionError as e:
        logger.warning(f"VectorStore 연결 실패, 빈 결과 반환: {e}")
        return {"rag_documents": [], "errors": [...]}

    except Exception as e:
        logger.exception("예상치 못한 검색 오류")
        return {"rag_documents": [], "errors": [...]}
```

---

## 11. 타입 힌트 규칙

### 11.1 반환 타입

```python
# 노드 함수는 State 타입을 명시적으로 반환
def node_name(state: StateType) -> StateType:
    return StateType(field=value)

# graph.py의 get_graph는 CompiledGraph 반환
from langgraph.graph.state import CompiledStateGraph

def get_graph(*, checkpointer=None) -> CompiledStateGraph:
    ...
```
