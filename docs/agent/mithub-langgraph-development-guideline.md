# MitHub LangGraph Development Guideline

> 목적: LangGraph 그래프/노드 추가 시 일관된 절차와 수정 위치를 제공한다.
> 대상: LangGraph 그래프/노드 구현자.
> 범위: 디렉토리 구조, 개발 절차, 파일 수정 가이드, 체크리스트.
> 비범위: 네이밍/코딩 규칙 및 아키텍처 결정.
> 관련 문서: [MitHub LangGraph Coding Convention](./mithub-langgraph-coding-convention.md), [MitHub LangGraph Architecture](./mithub-langgraph-architecture.md)

---

## 1. 디렉토리 구조

```
backend/app/infrastructure/graph/
├── __init__.py
├── main.py              # 실행 엔트리포인트 (app.invoke 등)
├── config.py            # 환경변수, 상수, 하이퍼파라미터
│
├── schema/
│   ├── __init__.py
│   └── models.py        # Pydantic 모델 등 공통 데이터 구조
│
├── utils/
│   ├── llm_factory.py   # LLM 모델 초기화/설정 로직
│   └── api_clients.py   # 외부 API 클라이언트
│
├── tools/               # 단순 함수형 도구들 (서브그래프 아님)
│   └── calculator.py
│
└── workflows/           # orchestration 및 서브그래프 모음
    ├── __init__.py
    │
    ├── orchestration/   # 메인 그래프
    │   ├── state.py     # OrchestrationState (루트 State)
    │   ├── connect.py   # 노드 연결, 라우팅 로직 (내부용)
    │   ├── graph.py     # 컴파일된 그래프 (외부 공개)
    │   └── nodes/       # 노드 함수들 (하위 모듈 허용)
    │       ├── answering.py
    │       ├── planning.py
    │       └── routing.py
    │
    ├── rag/             # RAG 서브그래프
    │   ├── state.py
    │   ├── connect.py
    │   ├── graph.py
    │   └── nodes/
    │       ├── retrieval.py
    │       └── generation.py
    │
    └── mit_search/      # Search 서브그래프
        ├── state.py
        ├── connect.py
        ├── graph.py
        └── nodes/
            ├── pre_retrieval.py
            └── retrieval.py
```

### 디렉토리별 역할

| 디렉토리 | 역할 | 예시 |
|---------|------|------|
| `schema/` | 전역 Pydantic 모델 정의 | `PlanningOutput`, `RoutingDecision` |
| `utils/` | LLM, API 클라이언트 등 공통 유틸 | `get_*_llm()`, `get_embeddings()` |
| `tools/` | 단순 함수형 도구 (그래프 아님) | `calculate()`, `format_date()` |
| `workflows/orchestration/` | 메인 그래프 | 라우팅, 최종 응답 생성 |
| `workflows/rag/` | RAG 서브그래프 | 문서 검색, 답변 생성 |
| `workflows/mit_search/` | 검색 서브그래프 | 쿼리 재작성, 검색 실행 |

### 파일별 공개 범위

| 파일명 | 용도 | 공개 여부 |
|-------|------|----------|
| `graph.py` | 컴파일된 그래프 객체 | 외부 공개 |
| `nodes/` | 노드 함수 정의 | 내부용 |
| `state.py` | 해당 워크플로우 전용 State | 내부용 |
| `connect.py` | 노드 연결, 라우팅 로직 (Edge) | 내부용 |

---

## 2. 목적

- 새 Agent/Node를 추가할 때 일관된 구조로 개발/리뷰/테스트가 가능하도록 한다.
- 서브그래프 분리를 통해 결합도를 낮추고, 순환 의존과 state 키 난립을 방지한다.
- 구조/의존 규칙을 고정해 불필요한 소통 비용을 구조적으로 제거한다.

---

## 3. 노드 추가 개발 워크플로우

### 3.1 노드 계약(Contract) 정의

Contract는 docstring 형식으로 고정한다. 상세 형식은 [MitHub LangGraph Coding Convention](./mithub-langgraph-coding-convention.md)을 따른다.

- 노드가 읽는 값(state 키), 쓰는 값(state 키)을 먼저 정의한다.
- 외부 부작용(DB/외부 API/스토리지/웹소켓 등)과 실패 정책(재시도/폴백/라우팅 변경/에러 기록)을 함께 적는다.

```python
# workflows/<name>/nodes/retrieval.py
def retrieve_documents(state: RagState) -> RagState:
    """관련 문서를 벡터스토어에서 검색

    Contract:
        reads: rag_query, messages
        writes: rag_documents
        side-effects: VectorStore 조회
        failures: RETRIEVAL_FAILED -> errors 기록
    """
```

### 3.2 state.py에 키 계약 반영

- 각 워크플로우는 state.py에서 사용하는 모든 state 키를 선언한다. (새 키 추가 시 state.py 수정이 선행)
- 각 키는 반드시 Annotated로 설명/메타데이터를 포함한다. (최소: desc)
- 서브그래프 전용 키는 prefix를 강제한다: `rag_*`, `mit_search_*` 등. (상세 규칙은 코딩 컨벤션 참고)
- 여러 워크플로우에서 재사용되는 복합 데이터 구조는 `schema/`의 Pydantic 모델로 정의하고, state에서는 그 모델 타입을 참조한다.

**State 규칙:**
- 서브그래프 State는 OrchestrationState를 상속한다.
- 서브그래프 전용 State는 `workflows/<subgraph>/state.py`에 둔다.
- 서브그래프 전용 필드는 `<subgraph>_` prefix를 사용한다.
- 누적 필드는 reducer(`Annotated[list[T], add]`)를 사용한다.
- 공용 복합 모델은 `schema/`에 정의한다.

### 3.3 노드 구현 (workflows/<name>/nodes/)

- 노드는 명시적으로 State 타입을 사용하여 반환한다. (`<StateType>(field=value)` 형태)
- 노드 코드는 `nodes/` 디렉토리에만 둔다. 필요 시 `nodes/<submodule>/`로 세분화한다.
  - 예: `nodes/indexing/`, `nodes/pre_retrieval/`, `nodes/retrieval/`
- 외부 연동/초기화 로직은 `utils/`, 단순 계산/가공은 `tools/`로 분리한다.
- 노드 네이밍/로깅/비동기/타입 규칙은 코딩 컨벤션을 따른다.

**예시: State 타입 반환 + state 읽기/쓰기 최소화**

```python
def generate_answer(state: OrchestrationState) -> OrchestrationState:
    """최종 응답 생성

    Contract:
        reads: messages, rag_context
        writes: messages
        side-effects: LLM API 호출
        failures: GENERATION_FAILED -> errors 기록
    """
    context = state.get("rag_context", "")
    messages = state["messages"]

    llm = get_generator_llm()
    response = llm.invoke(build_prompt(messages, context))

    return OrchestrationState(messages=[response])
```

### 3.4 서브그래프 통합 방식 선택

**권장**: 부모 그래프의 하나의 노드로서 서브그래프가 참가한다.

- 참고: [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#add-a-graph-as-a-node)
- `builder.add_node('node_name', compiled_graph)` 형태로 참가한다.

> **대안**: 서브그래프를 "노드처럼" 직접 그래프에 붙이는 방식은, state 계약이 안정화된 이후에만 고려한다.

통합 방식 비교/결정 근거는 [MitHub LangGraph Architecture](./mithub-langgraph-architecture.md)를 참고한다.

### 3.5 connect.py에 연결 추가

- connect.py에는 노드 연결(엣지)만 추가한다.
- 라우팅 함수는 `nodes/routing.py`에 정의하고, `conditional_edge`에 직접 연결한다. (노드로 등록하지 않음)

**예시: 노드 등록 + 조건부 엣지**

```python
# connect.py
from .nodes.routing import route_intent

builder.add_node("planner", create_plan)
builder.add_node("generator", generate_answer)

# 서브그래프 등록
builder.add_node("rag", rag_graph)
builder.add_node("mit_search", mit_search_graph)

builder.add_edge(START, "planner")

# 라우팅 함수를 conditional_edge에 직접 연결
builder.add_conditional_edges(
    "planner",
    route_intent,  # 라우팅 함수 (노드 아님)
    {"rag": "rag", "mit_search": "mit_search", "generator": "generator"},
)
```

### 3.6 graph.py / main.py 노출

- graph.py는 그래프 빌드/컴파일의 공개 API만 제공한다.
- 서브그래프는 체크포인터 없이 컴파일하고, 부모 그래프와 공유한다.
- main.py는 실행 엔트리포인트(invoke/ainvoke)를 단일화한다.
- 호출 시 필요한 실행 메타데이터(thread_id 등)는 config로 전달하고, state에 섞지 않는다.

**예시: Graph 생성 과정**

```python
# workflows/orchestration/graph.py
from .connect import build_orchestration

def get_graph(*, checkpointer=None):
    builder = build_orchestration()
    return builder.compile(checkpointer=checkpointer)

# main.py
from .workflows.orchestration.graph import get_graph

async def run(user_input: str, *, thread_id: str):
    graph = get_graph()
    state = {"messages": [{"role": "user", "content": user_input}]}
    cfg = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(state, config=cfg)
```

---

## 4. 공통 모듈 수정 가이드 (필요 시)

### 4.1 schema/models.py

- 여러 워크플로우에서 재사용되는 복합 데이터 구조는 `schema/models.py`에 정의한다.
- 네이밍 규칙은 코딩 컨벤션의 클래스/타입 규칙을 따른다.

```python
# schema/models.py
class RoutingDecision(BaseModel):
    next: str
    reason: str
```

### 4.2 config.py

- 환경변수 접근은 `GraphSettings`를 통해서만 한다.
- 기본값과 범위는 명시적으로 설정한다.

```python
# config.py
class GraphSettings(BaseSettings):
    llm_model: str = "gpt-4o-mini"

    class Config:
        env_prefix = "GRAPH_"
```

### 4.3 utils/llm_factory.py

- 베이스 LLM을 만들고, 용도별 설정은 `.bind()`로 분리한다.
- 노드에서는 직접 생성하지 않고 `get_*_llm()` 계열 함수를 사용한다.

```python
# utils/llm_factory.py
@lru_cache
def get_base_llm(model: str | None = None) -> ChatOpenAI:
    return ChatOpenAI(model=model or get_settings().llm_model)

def get_planner_llm() -> BaseChatModel:
    return get_base_llm().bind(temperature=0.3)
```

---

## 5. 체크리스트

### 새 노드 추가 시

- [ ] **노드 함수명**: `동사_목적어` 형태인가?
- [ ] **동사**: 원형 동사인가? (동명사 X, 과거형 X)
- [ ] **동사 적절성**: 카테고리에 맞는 동사인가?
- [ ] **Contract docstring**: reads/writes/side-effects/failures 명시
- [ ] **에러 코드**: `UPPER_SNAKE_CASE`, `행위_결과` 형태
- [ ] **반환**: `<StateType>(field=value)` 형태
- [ ] **LLM**: `get_*_llm()` 사용
- [ ] **환경변수**: `config.py` 경유

### 새 서브그래프 추가 시

- [ ] **디렉토리명**: 명사/명사구인가?
- [ ] **State 클래스**: `<Name>State` 형태, OrchestrationState 상속
- [ ] **State 필드 prefix**: 서브그래프명 prefix 사용
- [ ] **add_node 등록명**: 행위자는 역할 명사, 서브그래프는 디렉토리명인가? (라우팅 함수는 노드로 등록하지 않음)
- [ ] **graph.py**: 체크포인터 없이 컴파일
- [ ] **orchestration connect.py**: `add_node("name", graph)` 등록
