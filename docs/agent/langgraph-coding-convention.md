# LangGraph 코딩 컨벤션 (v2.0)

**결정사항**: 서브그래프는 `add_node("name", compiled_graph)` 방식으로 연결

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
| **저장/기록** | `save`, `store`, `record`, /`persist` | 영구 저장 | `save_result`, `record_decision` |

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
| **시작 노드** | `prepare_*`, `initialize_*` | `prepare_context`, `initialize_state` |
| **종료 노드** | `finalize_*`, `complete_*` | `finalize_response`, `complete_workflow` |
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

```
<워크플로우명>State

예시:
- OrchestrationState
- RagState
- MitSearchState
```

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

## 6. 전체 네이밍 체계 요약

```
infrastructure/graph/
├── main.py                          # 엔트리포인트
├── config.py                        # 설정 (UPPER_SNAKE 상수)
│
├── schema/
│   └── models.py                    # PascalCase 클래스
│       ├── RoutingDecision          # *Decision
│       ├── PlanOutput               # *Output
│       ├── Document                 # 도메인 명사
│       └── ErrorRecord              # *Record
│
├── utils/
│   └── llm_factory.py               # snake_case 함수
│       ├── get_llm()                # get_* 패턴
│       └── get_embeddings()
│
└── workflows/
    ├── orchestration/               # 시스템명 (메인)
    │   ├── state.py
    │   │   └── OrchestrationState   # PascalCase + State 접미사
    │   ├── connect.py
    │   │   └── build_orchestration()# build_* 패턴
    │   ├── graph.py
    │   │   └── get_graph()          # get_* 패턴
    │   └── nodes/
    │       ├── planning.py          # 기능 명사
    │       │   └── create_plan()    # 동사_목적어
    │       ├── routing.py
    │       │   └── route_intent()   # 동사_목적어
    │       └── answering.py
    │           └── generate_answer() # 동사_목적어
    │
    └── rag/                         # 명사 (약어)
        ├── state.py
        │   └── RagState             # prefix: rag_*
        └── nodes/
            ├── retrieval.py
            │   └── retrieve_documents()
            └── generation.py
                └── generate_rag_answer()
```

---

## 7. 디렉토리 구조

```
backend/app/infrastructure/graph/
├── __init__.py
├── main.py                    # 실행 엔트리포인트 (외부 공개)
├── config.py                  # 환경변수, 상수, 하이퍼파라미터
│
├── schema/                    # 공유 Pydantic 모델
│   ├── __init__.py
│   └── models.py              # PlanOutput, RoutingDecision, ErrorRecord 등
│
├── utils/
│   ├── __init__.py
│   ├── llm_factory.py         # get_llm(), get_embeddings()
│   └── api_clients.py         # 외부 API 클라이언트
│
├── tools/                     # 단순 함수형 도구 (그래프 아님)
│   ├── __init__.py
│   └── calculator.py
│
└── workflows/
    ├── __init__.py
    │
    ├── orchestration/         # 메인 그래프 (루트, 시스템명)
    │   ├── __init__.py
    │   ├── state.py           # OrchestrationState (최상위)
    │   ├── connect.py         # 노드/서브그래프 연결
    │   ├── graph.py           # 컴파일된 그래프 (외부 공개)
    │   └── nodes/
    │       ├── __init__.py
    │       ├── planning.py
    │       ├── routing.py
    │       └── answering.py
    │
    ├── rag/                   # RAG 서브그래프
    │   ├── __init__.py
    │   ├── state.py           # RagState(OrchestrationState) 상속
    │   ├── connect.py
    │   ├── graph.py
    │   └── nodes/
    │       ├── __init__.py
    │       ├── retrieval.py
    │       └── generation.py
    │
    └── mit_search/            # Search 서브그래프
        ├── __init__.py
        ├── state.py           # MitSearchState(OrchestrationState) 상속
        ├── connect.py
        ├── graph.py
        └── nodes/
            ├── __init__.py
            ├── pre_retrieval.py
            └── retrieval.py
```

---

## 8. State 정의

### 8.1 OrchestrationState (루트)

```python
# workflows/orchestration/state.py
"""오케스트레이션 State - 최상위 그래프 상태

모든 서브그래프는 이 State를 상속해야 한다.
(add_node 방식은 부모/자식 스키마 호환 필수)
"""

from typing import Annotated, TypedDict
from operator import add

from langgraph.graph.message import add_messages

from ...schema.models import PlanOutput, RoutingDecision, EvidenceRef, ErrorRecord


class OrchestrationState(TypedDict, total=False):
    """오케스트레이션 State

    Attributes:
        messages: 대화 메시지 (add_messages reducer)
        routing: 라우터 결정 {next, reason}
        tools: 서브그래프 출력 네임스페이스
        plan: 플래닝 결과
        evidence_refs: 근거 묶음 (누적)
        cursor: 증분 처리 커서
        errors: 에러 기록
    """
    # 필수
    messages: Annotated[list, add_messages]
    routing: RoutingDecision | None
    tools: dict  # {"rag": {...}, "mit_search": {...}}

    # 선택
    plan: PlanOutput | None
    evidence_refs: Annotated[list[EvidenceRef], add]
    cursor: dict | None  # {"transcript_seq": int}
    errors: Annotated[list[ErrorRecord], add] | None
```

### 8.2 서브그래프 State (상속)

```python
# workflows/rag/state.py
"""RAG 서브그래프 State"""

from typing import Annotated
from operator import add

from ..orchestration.state import OrchestrationState
from ...schema.models import Document


class RagState(OrchestrationState):
    """RAG State - OrchestrationState 상속

    add_node 방식 사용 시 부모와 스키마 호환 필수.
    전용 필드는 rag_ prefix 사용.
    """
    rag_query: str | None
    rag_documents: Annotated[list[Document], add]
    rag_context: str | None
```

```python
# workflows/mit_search/state.py
"""MIT Search 서브그래프 State"""

from typing import Annotated
from operator import add

from ..orchestration.state import OrchestrationState
from ...schema.models import SearchResult


class MitSearchState(OrchestrationState):
    """MIT Search State - OrchestrationState 상속

    전용 필드는 mit_search_ prefix 사용.
    """
    mit_search_query: str | None
    mit_search_results: Annotated[list[SearchResult], add]
    mit_search_filters: dict | None  # {"date_from": ..., "team_id": ...}
```

### 8.3 State 규칙

| 규칙 | 설명 |
|-----|------|
| **서브그래프는 상속** | `class SubState(OrchestrationState)` |
| **전용 필드 prefix** | `rag_*`, `mit_search_*` |
| **누적 필드는 reducer** | `Annotated[list[T], add]` |
| **복합 타입은 schema/** | Pydantic 모델로 정의 |

---

## 9. Node 정의

### 9.1 노드 계약 (Contract)

> **원칙**: Contract는 **docstring 형식으로 고정**한다.

```python
# workflows/orchestration/nodes/routing.py
"""라우터 노드"""

from typing import TYPE_CHECKING

from ....utils.llm_factory import get_router_llm
from ....schema.models import RoutingDecision

if TYPE_CHECKING:
    from ..state import OrchestrationState


def route_intent(state: "OrchestrationState") -> dict:
    """다음 실행 경로 결정

    Contract:
        reads: messages, plan
        writes: routing
        side-effects: none
        failures: -> routing.next = "fallback"
    """
    messages = state["messages"]
    last_msg = messages[-1].content if messages else ""

    if "검색" in last_msg or "찾아" in last_msg:
        next_node, reason = "rag", "검색 키워드 감지"
    elif "회의" in last_msg:
        next_node, reason = "mit_search", "회의 관련 질의"
    else:
        next_node, reason = "answering", "일반 대화"

    return {
        "routing": RoutingDecision(next=next_node, reason=reason)
    }
```

### 9.2 서브그래프 노드

```python
# workflows/rag/nodes/retrieval.py
"""검색 노드"""

import logging

from ....utils.llm_factory import get_embeddings
from ....config import RAG_TOP_K
from ....schema.models import Document, ErrorRecord

logger = logging.getLogger(__name__)


def retrieve_documents(state: "RagState") -> dict:
    """문서 검색

    Contract:
        reads: rag_query, messages
        writes: rag_documents, errors
        side-effects: VectorStore 조회
        failures: ConnectionError -> errors 기록
    """
    query = state.get("rag_query") or state["messages"][-1].content

    try:
        # 검색 로직
        documents = _search_vector_store(query)
        return {"rag_documents": documents}

    except Exception as e:
        logger.exception(f"검색 실패: {e}")
        return {
            "rag_documents": [],
            "errors": [ErrorRecord(
                node="retrieve_documents",
                error_type="RETRIEVAL_FAILED",
                message=str(e),
                recoverable=True,
            )]
        }
```

### 9.3 노드 규칙

| 규칙 | O | X |
|-----|---|---|
| 반환 타입 | `dict` (패치) | 전체 state |
| 함수 형태 | `def node(state) -> dict` | 클래스 |
| LLM 초기화 | `get_llm()` | 직접 생성 |
| 환경변수 | `config.py` | `os.getenv()` |
| 에러 처리 | `errors` 필드 기록 | raise |

---

## 10. connect.py 작성

### 10.1 노드 등록명 규칙

> **원칙**: 행위자 노드는 **역할 중심 명사**, 시스템(서브그래프)은 **디렉토리명(명사)** 그대로

| 항목 | 네이밍 | 예시 |
|-----|-------|-----|
| 파일명 | 기능 명사 | `planning.py`, `routing.py` |
| 노드 함수 | 동사_목적어 | `create_plan()`, `route_intent()` |
| **등록명** | **행위자 노드는 역할 중심 명사** | `"planner"`, `"intent_router"` |
| 서브그래프 등록명 | 디렉토리명 | `"rag"`, `"mit_search"` |

```python
# workflows/orchestration/connect.py
"""오케스트레이션 그래프 연결"""

from langgraph.graph import StateGraph, START, END

from .state import OrchestrationState
from .nodes.planning import create_plan
from .nodes.routing import route_intent
from .nodes.answering import generate_answer

# 서브그래프 import (컴파일된 그래프)
from ..rag.graph import rag_graph
from ..mit_search.graph import mit_search_graph


def build_orchestration() -> StateGraph:
    """오케스트레이션 그래프 빌드

    Flow:
        START -> planner -> intent_router --rag--> rag -> generator -> END
                                           --mit_search--> mit_search -> generator
                                           --answering--> generator
    """
    builder = StateGraph(OrchestrationState)

    # 노드 등록 (등록명 = 역할 중심 명사)
    builder.add_node("planner", create_plan)
    builder.add_node("intent_router", route_intent)
    builder.add_node("generator", generate_answer)

    # 서브그래프 등록 (add_node 방식)
    builder.add_node("rag", rag_graph)
    builder.add_node("mit_search", mit_search_graph)

    # 엣지
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "intent_router")

    # 조건부 엣지 (routing 필드의 next 값으로 분기)
    builder.add_conditional_edges(
        "intent_router",
        lambda s: s["routing"].next,
        {
            "rag": "rag",
            "mit_search": "mit_search",
            "answering": "generator",
            "fallback": "generator",
        },
    )

    builder.add_edge("rag", "generator")
    builder.add_edge("mit_search", "generator")
    builder.add_edge("generator", END)

    return builder
```

### 10.2 connect.py 규칙

| 규칙 | 설명 |
|-----|------|
| **노드 등록명** | 역할 중심 명사 (`"planner"`, `"intent_router"`) |
| **서브그래프 등록명** | 디렉토리명과 동일 (`"rag"`, `"mit_search"`) |
| **로직은 nodes/** | connect.py에는 연결만 |
| **조건부 엣지** | `lambda s: s["routing"].next` 형태 |
| **docstring** | ASCII 플로우 다이어그램 포함 |

---

## 11. graph.py 작성

```python
# workflows/orchestration/graph.py
"""오케스트레이션 그래프 - 외부 공개"""

from langgraph.checkpoint.memory import MemorySaver

from .connect import build_orchestration


def get_graph(*, checkpointer=None):
    """컴파일된 그래프 반환"""
    builder = build_orchestration()
    return builder.compile(checkpointer=checkpointer)


# 기본 인스턴스
orchestration_graph = get_graph(checkpointer=MemorySaver())
```

```python
# workflows/rag/graph.py
"""RAG 서브그래프 - 외부 공개"""

from .connect import build_rag


def get_graph(*, checkpointer=None):
    """컴파일된 RAG 그래프 반환"""
    builder = build_rag()
    return builder.compile(checkpointer=checkpointer)


# 서브그래프는 체크포인터 없이 컴파일 (부모와 공유)
rag_graph = get_graph()
```

---

## 12. main.py 작성

```python
# main.py
"""실행 엔트리포인트"""

from uuid import uuid4

from .workflows.orchestration.graph import get_graph
from .workflows.orchestration.state import OrchestrationState


async def run(
    user_input: str,
    *,
    thread_id: str | None = None,
    checkpointer=None,
) -> dict:
    """그래프 실행

    Args:
        user_input: 사용자 입력
        thread_id: 스레드 ID (없으면 자동 생성)
        checkpointer: 체크포인트 저장소

    Returns:
        최종 상태
    """
    graph = get_graph(checkpointer=checkpointer)

    initial_state: OrchestrationState = {
        "messages": [{"role": "user", "content": user_input}],
        "routing": None,
        "tools": {},
        "plan": None,
        "evidence_refs": [],
        "cursor": None,
        "errors": [],
    }

    config = {
        "configurable": {
            "thread_id": thread_id or str(uuid4()),
        }
    }

    return await graph.ainvoke(initial_state, config=config)
```

---

## 13. schema/models.py 작성

```python
# schema/models.py
"""공유 Pydantic 모델"""

from datetime import datetime
from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    """라우터 결정"""
    next: str
    reason: str


class PlanOutput(BaseModel):
    """플래닝 결과"""
    steps: list[str] = Field(default_factory=list)
    requires_search: bool = False
    requires_rag: bool = False


class Document(BaseModel):
    """검색 문서"""
    id: str
    content: str
    score: float = Field(ge=0, le=1)
    metadata: dict = Field(default_factory=dict)


class ErrorRecord(BaseModel):
    """에러 기록"""
    node: str
    error_type: str  # UPPER_SNAKE_CASE
    message: str
    recoverable: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

## 14. config.py 작성

```python
# config.py
"""그래프 설정"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class GraphSettings(BaseSettings):
    """그래프 설정"""
    # LLM
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7

    # RAG
    rag_top_k: int = 5
    rag_threshold: float = 0.7

    # Search
    search_max_results: int = 10

    # 실행
    max_retries: int = 3
    timeout_seconds: int = 30

    class Config:
        env_prefix = "GRAPH_"


@lru_cache
def get_settings() -> GraphSettings:
    return GraphSettings()


# 편의용 상수
settings = get_settings()
LLM_MODEL = settings.llm_model
RAG_TOP_K = settings.rag_top_k
```

---

## 15. utils/llm_factory.py 작성

> **패턴**: 베이스 모델 생성 후 용도별 `.bind()` 바인딩

```python
# utils/llm_factory.py
"""LLM 팩토리 - 베이스 모델 + 바인딩 패턴"""

from functools import lru_cache
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.language_models import BaseChatModel

from ..config import get_settings


@lru_cache
def get_base_llm(model: str | None = None) -> ChatOpenAI:
    """베이스 LLM 인스턴스 (캐싱)

    용도별 설정은 .bind()로 바인딩하여 사용.
    """
    s = get_settings()
    return ChatOpenAI(model=model or s.llm_model)


# === 용도별 바인딩된 모델 ===

def get_planner_llm() -> BaseChatModel:
    """플래닝용 LLM (낮은 temperature)"""
    return get_base_llm().bind(temperature=0.3)


def get_generator_llm() -> BaseChatModel:
    """응답 생성용 LLM (중간 temperature)"""
    return get_base_llm().bind(temperature=0.7)


def get_router_llm() -> BaseChatModel:
    """라우팅용 LLM (낮은 temperature, 결정적)"""
    return get_base_llm().bind(temperature=0.0)


def get_creative_llm() -> BaseChatModel:
    """창의적 생성용 LLM (높은 temperature)"""
    return get_base_llm().bind(temperature=1.0)


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """Embeddings 인스턴스 (캐싱)"""
    return OpenAIEmbeddings()
```

### 15.1 LLM 사용 규칙

| 용도 | 함수 | temperature | 사용처 |
|-----|------|------------|-------|
| 플래닝 | `get_planner_llm()` | 0.3 | `create_plan` 노드 |
| 라우팅 | `get_router_llm()` | 0.0 | `route_intent` 노드 |
| 응답 생성 | `get_generator_llm()` | 0.7 | `generate_answer` 노드 |
| 창의적 생성 | `get_creative_llm()` | 1.0 | 요약, 재작성 등 |

### 15.2 노드에서 사용 예시

```python
# workflows/orchestration/nodes/planning.py
from ....utils.llm_factory import get_planner_llm

def create_plan(state: "OrchestrationState") -> dict:
    """실행 계획 수립"""
    llm = get_planner_llm()
    # ...
```

### 15.3 커스텀 바인딩이 필요한 경우

```python
# 특수한 설정이 필요한 경우 베이스 모델에서 직접 바인딩
from ....utils.llm_factory import get_base_llm

def special_node(state: "State") -> dict:
    llm = get_base_llm().bind(
        temperature=0.5,
        max_tokens=2000,
        stop=["\n\n"],
    )
    # ...
```

---

## 16. 노드 계약(Contract) 규칙

### 16.1 필수 주석 형식

```python
def retrieve_documents(state: "RagState") -> dict:
    """관련 문서를 벡터스토어에서 검색

    Contract:
        reads: rag_query, messages
        writes: rag_documents
        side-effects: VectorStore 조회
        failures: RETRIEVAL_FAILED -> errors 기록

    Args:
        state: RAG 그래프 상태

    Returns:
        {"rag_documents": [...]} 형태의 패치
    """
```

### 16.2 에러 코드 네이밍

> **원칙**: `UPPER_SNAKE_CASE`, `<행위>_<결과>` 형태

| 패턴 | 예시 |
|-----|-----|
| `*_FAILED` | `RETRIEVAL_FAILED`, `GENERATION_FAILED` |
| `*_EMPTY` | `CONTEXT_EMPTY`, `DOCUMENTS_EMPTY` |
| `*_INVALID` | `INPUT_INVALID`, `FORMAT_INVALID` |
| `*_TIMEOUT` | `LLM_TIMEOUT`, `API_TIMEOUT` |
| `*_NOT_FOUND` | `DOCUMENT_NOT_FOUND`, `MEETING_NOT_FOUND` |

---

## 17. 체크리스트

### 새 노드 추가 시

- [ ] **노드 함수명**: `동사_목적어` 형태인가?
- [ ] **동사**: 원형 동사인가? (동명사 X, 과거형 X)
- [ ] **동사 적절성**: 카테고리에 맞는 동사인가?
- [ ] **Contract docstring**: reads/writes/side-effects/failures 명시
- [ ] **에러 코드**: `UPPER_SNAKE_CASE`, `행위_결과` 형태
- [ ] **반환**: `dict` 패치 형태
- [ ] **LLM**: `get_llm()` 사용
- [ ] **환경변수**: `config.py` 경유

### 새 서브그래프 추가 시

- [ ] **디렉토리명**: 명사/명사구인가?
- [ ] **State 클래스**: `<Name>State` 형태, OrchestrationState 상속
- [ ] **State 필드 prefix**: 서브그래프명 prefix 사용
- [ ] **add_node 등록명**: 행위자는 역할 명사, 서브그래프는 디렉토리명인가?
- [ ] **graph.py**: 체크포인터 없이 컴파일
- [ ] **orchestration connect.py**: `add_node("name", graph)` 등록

---

## 18. add_node 방식 특징 요약

| 특징 | 설명 |
|-----|------|
| **State 병합** | 자동 (스키마 호환 필수 → 상속) |
| **체크포인트** | 부모와 공유 |
| **스트리밍** | 자동 지원 |
| **LangSmith** | 내부 구조 펼쳐서 표시 |
| **서브그래프 컴파일** | 체크포인터 없이 |

---

## 19. 비동기 규칙

### 19.1 async vs sync 선택 기준

| 상황 | 선택 | 이유 |
|-----|------|-----|
| LLM 호출 포함 | `async def` | I/O 바운드 작업 |
| DB/API 호출 포함 | `async def` | I/O 바운드 작업 |
| 순수 계산/변환 | `def` | CPU 바운드 작업 |
| 외부 호출 없음 | `def` | 불필요한 오버헤드 방지 |

### 19.2 예시

```python
# 비동기 노드 (LLM 호출)
async def generate_answer(state: "OrchestrationState") -> dict:
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
def route_intent(state: "OrchestrationState") -> dict:
    """라우팅 결정 (동기)

    Contract:
        reads: messages
        writes: routing
        side-effects: none
    """
    # 단순 조건 분기, LLM 미사용
    return {"routing": RoutingDecision(...)}
```

---

## 20. 로깅 규칙

### 20.1 로거 설정

```python
# 각 노드 파일 상단
import logging

logger = logging.getLogger(__name__)
```

### 20.2 로깅 레벨 가이드

| 레벨 | 용도 | 예시 |
|-----|------|-----|
| `DEBUG` | 상세 디버깅 정보 | 입력 state 내용, 중간 결과 |
| `INFO` | 주요 실행 흐름 | 노드 시작/종료, 분기 결정 |
| `WARNING` | 예상된 문제 | 폴백 실행, 빈 결과 |
| `ERROR` | 복구 가능한 에러 | API 실패 후 재시도 |
| `EXCEPTION` | 예상치 못한 에러 | 스택 트레이스 포함 |

### 20.3 예시

```python
def retrieve_documents(state: "RagState") -> dict:
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

## 21. 타입 힌트 규칙

### 21.1 TYPE_CHECKING 패턴

> 순환 참조 방지를 위해 State 타입은 `TYPE_CHECKING` 블록에서 import

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..state import OrchestrationState


def create_plan(state: "OrchestrationState") -> dict:
    """문자열 타입 힌트로 순환 참조 방지"""
    ...
```

### 21.2 반환 타입

```python
# 노드 함수는 항상 dict 반환
def node_name(state: "StateType") -> dict:
    return {"field": value}

# graph.py의 get_graph는 CompiledGraph 반환
from langgraph.graph.state import CompiledStateGraph

def get_graph(*, checkpointer=None) -> CompiledStateGraph:
    ...
```

---
