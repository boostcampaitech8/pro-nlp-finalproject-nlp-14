# LangGraph 개발 가이드라인

## 1. 목적

- 새 Agent/Node를 추가할 때 일관된 구조로 개발/리뷰/테스트가 가능하도록 한다.
- 서브그래프 분리를 통해 결합도를 낮추고, 순환 의존과 state 키 난립을 방지한다.
- 구조/의존 규칙을 고정해 불필요한 소통 비용을 구조적으로 제거한다.

---

## 2. 노드 추가 개발 워크플로우

### 2.1 노드 계약(Contract) 정의

Contract는 docstring 형식으로 고정한다.

- 노드가 읽는 값(state 키), 쓰는 값(state 키)을 먼저 정의한다.
- 외부 부작용(DB/외부 API/스토리지/웹소켓 등)과 실패 정책(재시도/폴백/라우팅 변경/에러 기록)을 함께 적는다.

```python
# workflows/<name>/nodes/routing.py
def route_intent(state: "OrchestrationState") -> dict:
    """라우팅 결정

    Contract:
        reads: messages, plan
        writes: routing
        side-effects: none
        failures: -> routing.next = "fallback"
    """
```

### 2.2 state.py에 키 계약 반영

- 각 워크플로우는 state.py에서 사용하는 모든 state 키를 선언한다. (새 키 추가 시 state.py 수정이 선행)
- 각 키는 반드시 Annotated로 설명/메타데이터를 포함한다. (최소: desc)
- 서브그래프 전용 키는 prefix를 강제한다: `rag_*`, `mit_search_*` 등.
- 여러 워크플로우에서 재사용되는 복합 데이터 구조는 `schema/`의 Pydantic 모델로 정의하고, state에서는 그 모델 타입을 참조한다.

### 2.3 노드 구현 (workflows/<name>/nodes/)

- 노드는 가능한 한 patch(dict) 반환으로 통일한다. (state 전체 mutation 지양)
- 노드 코드는 `nodes/` 디렉토리에만 둔다. 필요 시 `nodes/<submodule>/`로 세분화한다.
  - 예: `nodes/indexing/`, `nodes/pre_retrieval/`, `nodes/retrieval/`
- 외부 연동/초기화 로직은 `utils/`, 단순 계산/가공은 `tools/`로 분리한다.
- 노드 내부에서 환경변수 직접 접근(`os.getenv`) 금지 → `config.py` 경유

**예시: patch 반환 + state 읽기/쓰기 최소화**

```python
def route_intent(state: "OrchestrationState") -> dict:
    """라우팅 결정

    Contract:
        reads: messages
        writes: routing
        side-effects: none
        failures: -> routing.next = "fallback"
    """
    messages = state["messages"]
    last_msg = messages[-1].content if messages else ""

    if "검색" in last_msg or "찾아" in last_msg:
        next_node, reason = "rag", "검색 키워드 감지"
    else:
        next_node, reason = "generator", "일반 대화"

    return {"routing": RoutingDecision(next=next_node, reason=reason)}
```

### 2.4 서브그래프 통합 방식 선택

**권장**: 부모 그래프의 하나의 노드로서 서브그래프가 참가한다.

- 참고: [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#add-a-graph-as-a-node)
- `builder.add_node('node_name', compiled_graph)` 형태로 참가한다.

> **대안**: 서브그래프를 "노드처럼" 직접 그래프에 붙이는 방식은, state 계약이 안정화된 이후에만 고려한다.

### 2.5 connect.py에 연결 추가

- connect.py에는 노드 연결(엣지)만 추가한다.
- 라우팅/판단 로직은 가능하면 노드(예: `nodes/routing.py`)로 두고, 연결부는 최대한 단순하게 유지한다.

**예시: 노드 등록 + 조건부 엣지**

```python
# connect.py
builder.add_node("planner", create_plan)
builder.add_node("intent_router", route_intent)
builder.add_node("generator", generate_answer)

# 서브그래프 등록
builder.add_node("rag", rag_graph)
builder.add_node("mit_search", mit_search_graph)

builder.add_edge(START, "planner")
builder.add_edge("planner", "intent_router")
builder.add_conditional_edges("intent_router",
    lambda s: s["routing"].next,
    {"rag": "rag", "mit_search": "mit_search", "answering": "generator"},
)
```

### 2.6 graph.py / main.py 노출

- graph.py는 그래프 빌드/컴파일의 공개 API만 제공한다.
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
