# Orchestration 메모리세이버 추가 가이드

## 현재 문제
- `orchestration/connect.py`에서 `app = workflow.compile()` (checkpointer 없음)
- State가 휘발성으로 대화 이력 미보존

## 수정 방법

### 1. orchestration/connect.py 수정

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .nodes.answering import generate_answer
from .nodes.evaluation import evaluate_result
from .nodes.mit_tools import execute_mit_tools
from .nodes.planning import create_plan
from .state import OrchestrationState

# 워크플로우 생성
workflow = StateGraph(OrchestrationState)

# ... (노드 등록 및 엣지 연결 코드는 그대로) ...

# ✅ 메모리세이버 추가
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

### 2. graph/main.py 수정 (thread_id 추가)

```python
if __name__ == "__main__":
    import uuid
    from datetime import datetime

    print("=" * 50)
    print("종료하려면 'quit', 'exit', 'q' 를 입력하세요")
    print("=" * 50 + "\n")

    # ✅ 세션별 thread_id 생성
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    run_id = str(uuid.uuid4())
    user_id = "chat_user"

    while True:
        user_input = input("\n질문: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n프로그램을 종료합니다.")
            break

        if not user_input:
            continue

        try:
            # ✅ messages는 checkpointer가 자동 관리하므로 초기값만 전달
            initial_state = {
                "messages": [HumanMessage(content=user_input)],
                "run_id": run_id,
                "user_id": user_id,
                "executed_at": datetime.now(),
                "retry_count": 0,
            }

            # ✅ config에 thread_id 전달
            final_state = app.invoke(initial_state, config=config)

            # ... (출력 코드는 그대로) ...

        except Exception as e:
            print(f"\n실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
```

### 3. API 엔드포인트 수정 (예시)

```python
from uuid import UUID
from langchain_core.messages import HumanMessage
from app.infrastructure.graph.orchestration import app

@router.post("/{meeting_id}/chat")
async def send_message(
    meeting_id: UUID,
    content: str,
    user_id: UUID,
):
    # ✅ meeting_id를 thread_id로 사용 (회의별 대화 이력 분리)
    config = {"configurable": {"thread_id": str(meeting_id)}}
    
    initial_state = {
        "messages": [HumanMessage(content=content)],
        "user_id": str(user_id),
        "run_id": str(uuid.uuid4()),
        "executed_at": datetime.now(),
    }
    
    # ✅ 이전 대화 이력이 자동으로 로드됨
    final_state = app.invoke(initial_state, config=config)
    
    return {"response": final_state["response"]}
```

## 효과

### Before (메모리 없음)
```python
# 1번째 질문
user: "회의 요약해줘"
agent: "요약: ..."  # messages만 남음

# 2번째 질문  
user: "더 자세히 설명해줘"
agent: "무엇을 설명할까요?"  # ❌ 이전 맥락 모름
```

### After (메모리 있음)
```python
# 1번째 질문
user: "회의 요약해줘"
agent: "요약: ..."  # State 저장됨

# 2번째 질문
user: "더 자세히 설명해줘"  
agent: "요약 내용 중 X를 자세히 설명하면..."  # ✅ 이전 맥락 기억
```

## MIT Summary 서브그래프

**✅ 수정 불필요**: 서브그래프는 자동으로 부모의 checkpointer를 공유합니다.

```python
# mit_summary/graph.py (그대로 유지)
def get_mit_summary_graph(*, checkpointer=None):
    builder = build_mit_summary()
    return builder.compile(checkpointer=checkpointer)  # None으로 전달
```

## 참고: 다른 Checkpointer 옵션

### MemorySaver (현재 권장)
- 메모리에만 저장 (서버 재시작 시 사라짐)
- 개발/테스트 단계에 적합

### PostgresSaver (프로덕션 권장)
```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string("postgresql://...")
app = workflow.compile(checkpointer=checkpointer)
```

### SQLiteSaver (로컬 파일)
```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
app = workflow.compile(checkpointer=checkpointer)
```

## 주의사항

1. **thread_id는 세션 단위**: 같은 thread_id = 같은 대화 이력
2. **State 크기 주의**: 매 노드마다 전체 State 저장 (용량 증가)
3. **TTL 설정 권장**: 오래된 checkpoint 자동 삭제
4. **프로덕션에서는 DB 백엔드 사용**: MemorySaver는 휘발성

## 추가 기능

### Time Travel (특정 checkpoint로 되돌리기)
```python
# 특정 checkpoint부터 재실행
state = app.get_state(config)
app.update_state(config, {"retry_count": 0})
```

### Human-in-the-loop (중간 승인)
```python
# 노드에서 interrupt 설정
workflow.add_node("human_approval", interrupt_before=True)

# 실행 중 멈춤
state = app.invoke(initial_state, config=config)
# ... 사람의 승인 대기 ...
# 재개
final_state = app.invoke(None, config=config)
```
