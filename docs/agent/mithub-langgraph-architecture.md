# MitHub LangGraph Architecture

> 목적: MitHub의 LangGraph 기반 그래프 구조와 결정사항을 공유한다.
> 대상: 기획/개발 전원.
> 범위: 그래프 구조, 서브그래프 전략, 상태 설계, 디렉토리 구조.
> 비범위: 구현 규칙/개발 절차.
> 관련 문서: [MitHub Agent Overview](./mithub-agent-overview.md), [MitHub LangGraph Development Guideline](./mithub-langgraph-development-guideline.md), [MitHub LangGraph Coding Convention](./mithub-langgraph-coding-convention.md)

---

## 1. LangGraph 간략 설명

LangGraph는 LLM 기반 에이전트 워크플로우를 그래프로 모델링하는 프레임워크입니다.

그래프는 State, Nodes, Edges로 구성됩니다.

- **State**: 그래프 실행 동안 공유되는 작업 보드
  - 노드들이 State를 읽고, 일부 필드를 업데이트함
- **Node**: State → State patch 형태의 함수
  - 예: `create_plan`, `route_intent`, `retrieve_documents`, `generate_answer`
- **Edge**: 다음 노드로 이동하는 규칙
  - 조건부 엣지를 사용하여 복잡한 워크플로우를 설계할 수 있음 (순환형 워크플로우 설계 가능)

**LangGraph의 장점:**
- 상태 기반 라우팅이 명확해져서 복잡한 에이전트 흐름을 구조적으로 관리 가능
- 워크플로우를 서브그래프로 분리해 팀 단위 개발/확장에 유리
- 체크포인트 또는 재실행 같은 운영 관점 확장이 쉬움

---

## 2. 메인 그래프 + 서브그래프 사용 방식

MitHub에서는 하나의 거대한 그래프 대신, Orchestration(메인 그래프)와 기능별 서브그래프로 구성합니다.

### 2.1 메인 그래프 (Orchestration)의 역할

메인 그래프는 전체 요청을 받아 다음을 수행합니다.

1. 입력을 받아 Planning에서 실행 전략 수립
2. Router에서 (Planning 결과와 현재 State를 바탕으로) "ToolCall이 필요한가?", "RAG로 갈까?", "MIT Search로 갈까?" 등의 분기 결정 수행
3. 필요하면 서브 그래프를 호출하고 결과를 수집
4. 최종적으로 Answering(응답 생성) 또는 후속 액션(예: 기록 저장, 다음 단계 안내)으로 연결

> **Router 구현 방식:**
> - Router는 조건부 엣지로도 충분히 구현 가능함. 하지만 "왜 그 경로로 갔는지"가 State에 남지 않아, 디버깅/회고/재현이 어려울 수 있음.
> - 반면 Router를 노드로 구현하여, `state.routing`에 결정 결과와 근거를 기록할 수 있음. (이후 조건부 엣지로 해당 상태를 읽어 다음 노드로 이동)
> - **결정**: 우선 노드로 구현 후, 필요 없으면 조건부 엣지로 회귀

### 2.2 서브그래프의 역할

서브그래프는 특정 기능(RAG 등)을 독립적인 작은 그래프로 구현합니다.

- **장점**: 복잡도를 분산하고, 기능 단위로 테스트/개선/교체가 쉬워짐
- **입력**: OrchestrationState의 일부 혹은 서브그래프 전용 State (최소 하나의 필드는 부모의 상태를 포함)
- **출력**: OrchestrationState의 일부

#### 서브그래프 통합 방식 비교

| 특징 | 옵션 A: Wrapper Node (수동 invoke) | 옵션 B: Native Subgraph (add_node) |
|-----|-----------------------------------|-----------------------------------|
| 구현 코드 | `def call_sub(state): return sub.invoke(state)` | `builder.add_node("sub", compiled_graph)` |
| 상태(State) 관리 | 수동 매핑 필요 (입/출력 변환 용이) | 자동 병합 (부모/자식 스키마가 호환되어야 함) |
| 시각화 (LangSmith) | 단일 노드(함수)로 표시됨 (내부 구조 숨김) | 내부 구조가 확장되어 상세히 보임 |
| 체크포인트(Persistence) | 서브그래프 내부 상태는 별도로 관리됨 | 부모 그래프와 체크포인트/메모리 공유 |
| 스트리밍 | 수동으로 제너레이터 처리 필요 | 자동 지원 (부모의 스트리밍 설정 승계) |

**결정**: `add_node("mit_search", mit_search_graph)` 방식 사용

### 2.3 State 공유 전략

기본적으로 `workflows/orchestration/state.py`의 OrchestrationState를 루트 State로 사용합니다.

서브그래프가 복잡해지면 `workflows/<subgraph>/state.py`에 전용 State를 둘 수 있습니다.

- 전용 State는 OrchestrationState를 상속하거나, 최소한 호환 필드를 유지해야 함
- 순환 참조를 막기 위해 공통 모델은 `schema/`에만 둡니다.

### 2.4 왜 이런 구조를 채택했는가?

메인 그래프와 서브그래프로 이루어진 현재의 구조를 채택하기 전 다음 3가지 방식에 대해 고민했습니다.

| 방식 | 장점 | 단점 |
|-----|------|------|
| **MCP처럼 외부 프로그램으로 분리** | 격리성, 스케일링 쉬움 | State(메모리) 공유가 어려움, 네트워크 비용 발생, 개발 속도 느림, 높은 디버깅 난이도 |
| **그래프를 나누고 서브그래프를 호출** | State 공유가 자연스러움, 복잡도 분산, 서브그래프 단위 테스트, 점진적 확장 용이 | 초기 구조 설계 어려움, 서브그래프 과다 분할 위험 |
| **하나의 거대한 그래프** | 초기 빠른 구현, 이동 규칙을 한 눈에 확인할 수 있음 (그래프가 단순한 초기에만) | 그래프 비대화, 팀 병렬개발 어려움, 기능별 테스트 어려움 |

**결정**: 초기 구조 설계가 어려운 대신, State 공유가 용이하고 병렬 개발이 가능한 **메인 그래프 + 서브그래프(2번)** 구조가 가장 적합하다고 판단

---

## 3. 디렉토리 구조

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
| `schema/` | 전역 Pydantic 모델 정의 | `PlanOutput`, `RoutingDecision` |
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

## 4. OrchestrationState 스키마

```python
# OrchestrationState 필드 정의
messages: list[Message]                 # 대화 입력/출력 (필수)
plan: PlanOutput | None                 # planning 결과 (선택)
routing: RoutingDecision                # router 결정 (필수)
tools: dict                             # 서브그래프 출력 namespace (필수)
                                        # {"rag": {...}, "mit_search": {...}}
evidence_refs: list[EvidenceRef]        # 최종 근거 묶음 (선택)
cursor: dict | None                     # 증분 처리용 커서 (선택)
                                        # {"transcript_seq": int}
errors: list[ErrorRecord] | None        # 실패 기록/재시도 판단 (선택)
```

### State 규칙

- 서브그래프 State는 OrchestrationState를 상속한다.
- 서브그래프 전용 필드는 `<subgraph>_` prefix를 사용한다.
- 누적 필드는 reducer(`Annotated[list[T], add]`)를 사용한다.
- 공용 복합 모델은 `schema/`에 정의한다.

---

## 5. 향후 검토 사항

- OrchestrationState에 metadata (logging) 필드 추가 여부
- evaluator를 각각의 서브그래프에 둘지 혹은 하나의 독립적인 서브그래프로 구성할지
