# MitHub LangGraph Workflows

> 목적: MitHub의 LangGraph 기반 워크플로우 구조와 동작 방식을 설명한다.
> 대상: 기획/개발 전원.
> 범위: 워크플로우별 State, 노드, 그래프 흐름, Worker 통합, Neo4j 연동.
> 비범위: 개발 가이드라인, 코딩 규칙, 인프라 설정.
> 관련 문서: [MitHub Agent Overview](../mithub-agent-overview.md), [MitHub LangGraph Architecture](../mithub-langgraph-architecture.md)

---

## 목차

1. [워크플로우 개요](#1-워크플로우-개요)
2. [generate_pr 워크플로우](#2-generate_pr-워크플로우)
3. [mit_action 워크플로우](#3-mit_action-워크플로우)
4. [Worker 통합](#4-worker-통합)
5. [Neo4j 통합](#5-neo4j-통합)

---

## 1. 워크플로우 개요

MitHub는 회의 트랜스크립트에서 지식을 추출하고 구조화하는 3개의 LangGraph 워크플로우를 운영합니다.

### 1.1 워크플로우 목록

| 워크플로우 | 목적 | 입력 | 출력 | 트리거 |
|-----------|------|------|------|--------|
| `orchestration` | 사용자 질의에 대한 Agent 응답 생성 | 사용자 메시지 (Chat) | Agent 응답 | Chat API 호출 |
| `generate_pr` | 트랜스크립트에서 Agenda와 Decision 추출 | 회의 트랜스크립트 | Agenda + Decision IDs | POST /meetings/{id}/generate-pr |
| `mit_action` | Decision에서 Action Item 추출 (예정) | Decision 데이터 | Action Items | Decision 머지 완료 시 |

### 1.2 워크플로우 통합 구조

```
[STT 완료] → [Transcript 병합] → [트리거: generate_pr]
                                        ↓
                                  [Meeting-Agenda-Decision 생성]
                                        ↓
                                  [Decision 머지 시]
                                        ↓
                                  [트리거: mit_action]
                                        ↓
                                  [Action Items 생성]
                                        ↓
                                  [담당자 알림 / 외부 도구 연동 (예정)]
```

### 1.3 설계 원칙

**서브그래프 독립성**: 각 워크플로우는 독립적인 서브그래프로 구현되어 있음
- `generate_pr`: 단방향 파이프라인 (extraction → persistence)
- `mit_action`: 순환형 구조 (extraction → evaluation → retry/save)

**State 네이밍 규칙**: 서브그래프 전용 필드는 워크플로우명 prefix 사용
- `generate_pr_*`: generate_pr 워크플로우 전용 필드
- `mit_action_*`: mit_action 워크플로우 전용 필드

**노드 등록 규칙**: 노드는 역할 명사로 등록
- 함수명: `extract_agendas`, `save_to_kg` (동사+명사)
- 노드명: `"extractor"`, `"saver"` (명사)

---

## 2. generate_pr 워크플로우

회의 트랜스크립트에서 Agenda와 Decision을 추출하여 Neo4j에 저장하는 단방향 파이프라인입니다.

### 2.1 그래프 구조

```
START → extractor → saver → END
```

- **extractor**: 트랜스크립트에서 Agenda/Decision LLM 추출
- **saver**: Meeting-Agenda-Decision을 Neo4j에 원홉 저장

### 2.2 State 스키마 (GeneratePrState)

```python
class GeneratePrState(TypedDict, total=False):
    # 입력 필드
    generate_pr_meeting_id: str              # 회의 ID
    generate_pr_transcript_text: str         # 트랜스크립트 전문

    # 중간 상태 필드 (LLM 추출 결과)
    generate_pr_agendas: list[dict]          # 추출된 Agenda+Decision 데이터
    generate_pr_summary: str                 # 회의 요약

    # 출력 필드
    generate_pr_agenda_ids: list[str]        # 생성된 Agenda IDs
    generate_pr_decision_ids: list[str]      # 생성된 Decision IDs
```

### 2.3 노드 상세

#### 2.3.1 extractor (extract_agendas)

**위치**: `backend/app/infrastructure/graph/workflows/generate_pr/nodes/extraction.py`

**책임**: 트랜스크립트에서 Agenda와 Decision을 LLM으로 추출

**Contract**:
- **reads**: `generate_pr_transcript_text`
- **writes**: `generate_pr_agendas`, `generate_pr_summary`
- **side-effects**: LLM API 호출 (Clova Studio)
- **failures**: 추출 실패 시 빈 결과 반환 (`[]`)

**추출 데이터 구조**:
```python
{
    "summary": "회의 전체 요약 (2-3문장)",
    "agendas": [
        {
            "topic": "아젠다 주제",
            "description": "아젠다 설명",
            "decisions": [
                {
                    "content": "결정 내용",
                    "context": "결정 맥락/근거"
                }
            ]
        }
    ]
}
```

**Note**: 현재 추출 구조는 Agenda를 Meeting 하위에 직접 생성하는 단순화된 형태입니다. 도메인 모델 정의(`02-conceptual-model.md`)에 따르면:
- Agenda는 Team 레벨 엔티티 (`team_id` 보유, semantic matching용 embedding)
- Meeting과 Agenda 사이에 Minutes 엔티티가 중개 (Minutes M:N Agenda via MinutesAgenda)
- Decision은 `agenda_id`와 `minutes_id` 두 FK를 보유

현재 구현은 Minutes 노드를 생략하고 `(Meeting)-[:CONTAINS]->(Agenda)`로 직접 연결하고 있어, 도메인 정의와 불일치합니다. Neo4j 쿼리 및 추출 구조의 업데이트가 필요합니다.

**주요 로직**:
1. 트랜스크립트 길이 제한 (8000자, 토큰 제한 고려)
2. Pydantic 출력 파서 사용 (구조화된 추출)
3. LangChain 체인: `prompt | llm | parser`
4. 추출 실패 시 에러 로깅 + 빈 결과 반환 (워크플로우 중단하지 않음)

**로깅**:
- `INFO`: Agenda 추출 완료 (개수), Decision 추출 완료 (개수)
- `WARNING`: 트랜스크립트가 truncated됨
- `ERROR`: Agenda/Decision 추출 실패

#### 2.3.2 saver (save_to_kg)

**위치**: `backend/app/infrastructure/graph/workflows/generate_pr/nodes/persistence.py`

**책임**: Meeting-Agenda-Decision을 Neo4j에 원홉으로 저장

**Contract**:
- **reads**: `generate_pr_meeting_id`, `generate_pr_agendas`, `generate_pr_summary`
- **writes**: `generate_pr_agenda_ids`, `generate_pr_decision_ids`
- **side-effects**: Neo4j 쓰기 (1회 Cypher 쿼리)

**주요 로직**:
1. `KGRepository.create_minutes()` 호출 (Meeting-Agenda-Decision 원홉 생성)
2. 반환된 `KGMinutes`에서 `decision_ids` 추출
3. `agenda_ids`는 현재 반환하지 않음 (추후 개선 예정)

**Note**: 현재 구현에서 Minutes는 별도 노드 없이 Meeting + Agenda + Decision의 Projection으로 처리됩니다. 도메인 모델과의 정합성을 위해 Minutes 노드 도입 및 Neo4j 쿼리 업데이트가 필요합니다 (도메인 모델 참조: `02-conceptual-model.md`).

**로깅**:
- `INFO`: KG 저장 시작/완료
- `WARNING`: 추출된 agendas가 없음
- `ERROR`: meeting_id 없음, KG 저장 실패

### 2.4 그래프 컴파일

**위치**: `backend/app/infrastructure/graph/workflows/generate_pr/graph.py`

```python
generate_pr_graph = get_graph()
```

- 서브그래프이므로 checkpointer 없이 컴파일 (부모와 공유)
- `generate_pr_graph.ainvoke(state)` 형태로 호출

### 2.5 실행 예시

```python
result = await generate_pr_graph.ainvoke({
    "generate_pr_meeting_id": "meeting-uuid",
    "generate_pr_transcript_text": "트랜스크립트 전문...",
})

# result:
# {
#     "generate_pr_agenda_ids": ["agenda-1", "agenda-2"],
#     "generate_pr_decision_ids": ["decision-1", "decision-2", "decision-3"],
#     "generate_pr_summary": "회의 요약",
#     "generate_pr_agendas": [...]
# }
```

---

## 3. mit_action 워크플로우

Decision에서 Action Item을 추출하는 순환형 워크플로우입니다. 평가 실패 시 재시도 로직을 포함합니다.

### 3.1 그래프 구조

```
START → extractor → evaluator → [route_eval] → saver → END
           ↑                           |
           |___________________________|
                    (재시도)
```

- **extractor**: Decision에서 Action Item LLM 추출
- **evaluator**: 추출된 Action Item 품질 평가
- **route_eval**: 평가 결과에 따라 재시도 또는 저장 결정
- **saver**: Action Item을 GraphDB에 저장

### 3.2 State 스키마 (MitActionState)

```python
class MitActionState(TypedDict, total=False):
    # 입력 필드
    mit_action_decision: dict                        # Decision 데이터 (확정된 결정사항)
    mit_action_meeting_id: str                       # 회의 ID

    # 중간 상태 필드
    mit_action_raw_actions: list[dict]               # LLM이 추출한 raw Action Items
    mit_action_eval_result: ActionItemEvalResult     # 평가 결과
    mit_action_retry_reason: str | None              # 재시도 사유 (평가 실패 시)
    mit_action_retry_count: int                      # 재시도 횟수

    # 출력 필드
    mit_action_actions: list[ActionItemData]         # 저장된 Action Items
```

**ActionItemData 구조**:
```python
class ActionItemData(BaseModel):
    content: str                # 할 일 내용
    assignee_id: str | None     # 담당자 ID
    assignee_name: str | None   # 담당자 이름 (추론된)
    deadline: str | None        # 기한 (ISO 8601)
    confidence: float           # 추출 신뢰도 (0.0-1.0)
```

**ActionItemEvalResult 구조**:
```python
class ActionItemEvalResult(BaseModel):
    passed: bool      # 평가 통과 여부
    reason: str       # 평가 결과 사유
    score: float      # 평가 점수 (0.0-1.0)
```

### 3.3 노드 상세

#### 3.3.1 extractor (extract_actions)

**위치**: `backend/app/infrastructure/graph/workflows/mit_action/nodes/extraction.py`

**책임**: Decision에서 Action Item 추출

**Contract**:
- **reads**: `mit_action_decision`, `mit_action_retry_reason`
- **writes**: `mit_action_raw_actions`
- **side-effects**: LLM API 호출
- **failures**: EXTRACTION_FAILED → errors 기록

**재시도 처리**:
- `mit_action_retry_reason`이 있으면 로깅 후 재추출
- 재시도 시 평가 실패 사유를 프롬프트에 반영 (예정)

**현재 상태**: TODO (스켈레톤만 구현됨)

#### 3.3.2 evaluator (evaluate_actions)

**위치**: `backend/app/infrastructure/graph/workflows/mit_action/nodes/evaluation.py`

**책임**: 추출된 Action Item 품질 평가

**Contract**:
- **reads**: `mit_action_raw_actions`
- **writes**: `mit_action_eval_result`
- **side-effects**: LLM API 호출
- **failures**: EVALUATION_FAILED → errors 기록

**평가 기준** (예정):
1. 각 Action Item의 명확성 평가
2. 담당자 지정 적절성 평가
3. 기한 추출 정확성 평가
4. 전체 점수 산출 (0.0-1.0)

**현재 상태**: TODO (스켈레톤만 구현됨, 항상 `passed=True` 반환)

#### 3.3.3 route_eval (조건부 엣지)

**위치**: `backend/app/infrastructure/graph/workflows/mit_action/nodes/routing.py`

**책임**: 평가 결과에 따라 다음 노드 결정

**Contract**:
- **reads**: `mit_action_eval_result`, `mit_action_retry_count`
- **returns**: `"extractor"` (재시도) 또는 `"saver"` (저장 진행)

**라우팅 규칙**:
1. `eval_result`가 `None` → `"saver"` (경고 로깅)
2. `eval_result.passed == True` → `"saver"`
3. `retry_count >= MAX_RETRY (3)` → `"saver"` (최대 재시도 초과)
4. 그 외 → `"extractor"` (재시도)

**재시도 횟수 제한**: `MAX_RETRY = 3` (config.py)

**Note**: 라우팅 함수는 노드로 등록하지 않고 `conditional_edge`에 직접 연결

#### 3.3.4 saver (save_actions)

**위치**: `backend/app/infrastructure/graph/workflows/mit_action/nodes/persistence.py`

**책임**: Action Item을 GraphDB에 저장

**Contract**:
- **reads**: `mit_action_raw_actions`, `mit_action_meeting_id`, `mit_action_decision`
- **writes**: `mit_action_actions`
- **side-effects**: GraphDB 쓰기
- **failures**: SAVE_FAILED → errors 기록

**현재 상태**: TODO (스켈레톤만 구현됨, GraphDB 스키마 확정 후 구현 예정)

### 3.4 순환형 워크플로우 동작

```
1. extractor: Action Item 추출
2. evaluator: 품질 평가
3. route_eval:
   - passed=True → saver로 이동
   - passed=False and retry_count < 3 → extractor로 돌아감 (재시도)
   - passed=False and retry_count >= 3 → saver로 이동 (최대 재시도 초과)
4. saver: GraphDB 저장
```

**재시도 시 State 변화**:
```python
# 1차 시도
{
    "mit_action_retry_count": 0,
    "mit_action_raw_actions": [...],
    "mit_action_eval_result": {"passed": False, "reason": "담당자 불명확"}
}

# 2차 시도 (route_eval이 extractor로 라우팅)
{
    "mit_action_retry_count": 1,
    "mit_action_retry_reason": "담당자 불명확",
    "mit_action_raw_actions": [...],  # 재추출
    "mit_action_eval_result": {"passed": True, "reason": "품질 양호"}
}

# 3차 시도 (saver로 진행)
```

### 3.5 그래프 컴파일

**위치**: `backend/app/infrastructure/graph/workflows/mit_action/graph.py`

```python
mit_action_graph = get_graph()
```

- 서브그래프이므로 checkpointer 없이 컴파일 (부모와 공유)
- `mit_action_graph.ainvoke(state)` 형태로 호출

### 3.6 실행 예시

```python
result = await mit_action_graph.ainvoke({
    "mit_action_decision": {
        "id": "decision-uuid",
        "content": "UI 디자인을 다음 주까지 완료한다",
        "context": "사용자 피드백 반영"
    },
    "mit_action_meeting_id": "meeting-uuid",
})

# result:
# {
#     "mit_action_actions": [
#         ActionItemData(
#             content="UI 디자인 초안 작성",
#             assignee_id="user-1",
#             assignee_name="홍길동",
#             deadline="2026-02-03T00:00:00Z",
#             confidence=0.85
#         ),
#         ...
#     ],
#     "mit_action_retry_count": 1,  # 1회 재시도 후 성공
#     "mit_action_eval_result": {...}
# }
```

---

## 4. Worker 통합

LangGraph 워크플로우는 ARQ Worker를 통해 비동기 백그라운드 작업으로 실행됩니다.

### 4.1 Worker 태스크 목록

**위치**: `backend/app/workers/arq_worker.py`

| 태스크 함수 | 목적 | 트리거 시점 | 워크플로우 연결 |
|-----------|------|------------|---------------|
| `transcribe_recording_task` | 개별 녹음 STT 변환 | 녹음 완료 시 | - |
| `transcribe_meeting_task` | 회의 전체 STT 변환 | 수동 트리거 | - |
| `merge_utterances_task` | 화자별 발화 병합 | 모든 녹음 STT 완료 시 | - |
| `generate_pr_task` | PR 생성 | 수동 트리거 (POST /meetings/{id}/generate-pr) | **generate_pr 워크플로우** |
| `mit_action_task` | Action Item 추출 | Decision 머지 완료 시 | **mit_action 워크플로우** |

### 4.2 generate_pr_task

**책임**: STT 완료 후 Agenda + Decision 생성

**실행 흐름**:
```python
async def generate_pr_task(ctx: dict, meeting_id: str) -> dict:
    # 1. 트랜스크립트 조회
    transcript = await transcript_service.get_transcript(meeting_uuid)

    # 2. generate_pr 워크플로우 실행
    result = await generate_pr_graph.ainvoke({
        "generate_pr_meeting_id": meeting_id,
        "generate_pr_transcript_text": transcript.full_text or "",
    })

    # 3. 결과 로깅 및 반환
    return {
        "status": "success",
        "agenda_count": len(result["generate_pr_agenda_ids"]),
        "decision_count": len(result["generate_pr_decision_ids"]),
    }
```

**트리거 방식**: 수동 (API 엔드포인트)
- `POST /api/v1/meetings/{meeting_id}/generate-pr`
- STT 자동 트리거 제거됨 (race condition 방지)

**에러 처리**:
- 트랜스크립트 없음: `{"status": "failed", "error": "TRANSCRIPT_NOT_FOUND"}`
- 워크플로우 실패: 로그 기록 + 에러 반환

### 4.3 mit_action_task

**책임**: Decision에서 Action Item 추출

**실행 흐름**:
```python
async def mit_action_task(ctx: dict, decision_id: str) -> dict:
    # 1. Decision 데이터 조회
    decision = await kg_repo.get_decision(decision_id)

    # 2. mit_action 워크플로우 실행
    result = await mit_action_graph.ainvoke({
        "mit_action_decision": {
            "id": decision.id,
            "content": decision.content,
            "context": decision.context,
        },
        "mit_action_meeting_id": "",  # Decision에서 meeting_id 필요시 별도 조회
    })

    # 3. 결과 로깅 및 반환
    return {
        "status": "success",
        "action_count": len(result["mit_action_actions"]),
    }
```

**트리거 방식**: 자동 (Decision 머지 완료 시)
- PR Review에서 Decision 머지 완료 이벤트 수신
- ARQ 큐에 `mit_action_task` 작업 enqueue

**에러 처리**:
- Decision 없음: `{"status": "error", "message": "Decision not found"}`
- 워크플로우 실패: 로그 기록 + 에러 반환

### 4.4 Worker 설정

```python
class WorkerSettings:
    functions = [
        transcribe_recording_task,
        transcribe_meeting_task,
        merge_utterances_task,
        generate_pr_task,
        mit_action_task,
    ]

    max_tries = 3                    # 최대 재시도 횟수
    job_timeout = 3600               # 작업 타임아웃 (1시간)
    keep_result = 3600               # 결과 보관 시간 (1시간)
    health_check_interval = 60       # 헬스체크 간격 (60초)
```

### 4.5 작업 체이닝

**STT → generate_pr 체이닝 (수동)**:
```python
# transcribe_recording_task 완료 후
all_processed = await transcript_service.check_all_recordings_processed(meeting_id)
if all_processed:
    await transcript_service.merge_utterances(meeting_id)
    # PR 생성은 수동 트리거로 변경 (race condition 방지)
```

**generate_pr → mit_action 체이닝 (자동, 예정)**:
```python
# generate_pr_task 완료 후
# Decision 머지 이벤트 수신 시
await arq_pool.enqueue_job("mit_action_task", decision_id=decision_id)
```

---

## 5. Neo4j 통합

LangGraph 워크플로우는 Neo4j GraphDB를 사용하여 지식 그래프를 구성합니다.

### 5.1 Neo4j 접근 패턴

**Driver 획득**:
```python
from app.core.neo4j import get_neo4j_driver

driver = get_neo4j_driver()
```

**Repository 패턴**:
```python
from app.repositories.kg.repository import KGRepository

kg_repo = KGRepository(driver)
```

### 5.2 generate_pr 워크플로우의 Neo4j 사용

**노드**: `saver` (save_to_kg)

**사용 메서드**: `KGRepository.create_minutes()`

**동작**:
```python
minutes = await kg_repo.create_minutes(
    meeting_id=meeting_id,
    summary=summary,
    agendas=agendas,
)

# 1회 Cypher 쿼리로 Meeting-Agenda-Decision 원홉 생성
# MERGE (m:Meeting {id: $meeting_id})
# FOREACH (agenda IN $agendas |
#   CREATE (a:Agenda {id: randomUUID(), ...})
#   MERGE (m)-[:HAS_AGENDA]->(a)
#   FOREACH (decision IN agenda.decisions |
#     CREATE (d:Decision {id: randomUUID(), ...})
#     MERGE (a)-[:HAS_DECISION]->(d)
#   )
# )
```

**생성 노드**:
- `Meeting`: 회의 노드 (기존 노드와 MERGE)
- `Agenda`: 아젠다 노드 (새로 생성)
- `Decision`: 결정사항 노드 (새로 생성)

**생성 관계**:
- `(Meeting)-[:HAS_AGENDA]->(Agenda)`
- `(Agenda)-[:HAS_DECISION]->(Decision)`

### 5.3 mit_action 워크플로우의 Neo4j 사용 (예정)

**노드**: `extractor`, `saver`

**사용 메서드**:
- `KGRepository.get_decision(decision_id)`: Decision 조회
- `KGRepository.create_action_items()`: Action Item 저장 (예정)

**동작** (예정):
```python
# extractor: Decision 조회
decision = await kg_repo.get_decision(decision_id)

# saver: Action Item 저장
await kg_repo.create_action_items(
    decision_id=decision_id,
    actions=actions,
)

# FOREACH (action IN $actions |
#   CREATE (ai:ActionItem {id: randomUUID(), ...})
#   MERGE (d)-[:HAS_ACTION_ITEM]->(ai)
# )
```

**생성 노드** (예정):
- `ActionItem`: 액션 아이템 노드

**생성 관계** (예정):
- `(Decision)-[:HAS_ACTION_ITEM]->(ActionItem)`

### 5.4 Neo4j 트랜잭션 관리

**원홉 저장**: 1회 Cypher 쿼리로 전체 서브그래프 생성
- 장점: 트랜잭션 보장, 네트워크 오버헤드 최소화
- 단점: 쿼리 복잡도 증가

**에러 처리**: Neo4j 쓰기 실패 시 워크플로우 중단하지 않음
- 로그 기록 + 빈 결과 반환
- Worker가 재시도 처리 (최대 3회)

---

## 6. Realtime Worker 통합

회의 진행 중 실시간 STT 처리를 위한 별도 Worker 서비스입니다.

### 6.1 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Realtime Worker 아키텍처                       │
└─────────────────────────────────────────────────────────────────┘

[Client Browser]
      │
      │ WebRTC (LiveKit SFU)
      ▼
[LiveKit Room] ◀───────────────────────────────────────┐
      │                                                 │
      │ Audio Track Subscription                       │
      ▼                                                 │
[Realtime Worker]                                       │
      │                                                 │
      ├─▶ [Clova Speech STT] ─────▶ Transcript         │
      │         │                                       │
      │         └─▶ POST /api/v1/meetings/{id}/transcripts
      │                                                 │
      └─▶ VAD Events (DataPacket) ◀────────────────────┘
              │
              └─▶ epFlag=true (발화 종료 표시)
```

### 6.2 Worker 구성 요소

| 구성 요소 | 파일 | 역할 |
|-----------|------|------|
| **RealtimeWorker** | `worker/src/main.py` | 메인 오케스트레이션 |
| **LiveKitBot** | `worker/src/livekit.py` | LiveKit Room Bot 연결 |
| **ClovaSpeechSTTClient** | `worker/src/clients/stt.py` | Clova Speech gRPC 스트리밍 |
| **BackendAPIClient** | `worker/src/clients/backend.py` | Backend API 통신 |

### 6.3 Worker Manager

Worker 라이프사이클을 관리하는 추상화 레이어입니다.

**위치**: `backend/app/infrastructure/worker_manager/`

| 구현체 | 환경 | 사용 기술 |
|--------|------|-----------|
| `DockerWorkerManager` | 로컬/Docker Compose | Docker SDK |
| `K8sWorkerManager` | Kubernetes | K8s Job API |

**자동 선택 로직**:
```python
def get_worker_manager():
    if Path("/.dockerenv").exists():
        return DockerWorkerManager()
    else:
        return K8sWorkerManager()
```

### 6.4 Worker 라이프사이클

```
1. Meeting 시작 (room_started 웹훅)
   └─▶ worker_manager.start_worker(meeting_id)
        ├─▶ Docker: docker run -d --name realtime-worker-{meeting_id}
        └─▶ K8s: Create Job realtime-worker-{meeting_id}

2. Worker 실행
   └─▶ LiveKit Room에 Bot으로 참여
   └─▶ 참여자 오디오 트랙 구독
   └─▶ Clova Speech gRPC 스트리밍
   └─▶ 실시간 Transcript → Backend API

3. Meeting 종료 (room_finished 웹훅, 30초 후)
   └─▶ worker_manager.stop_worker(worker_id)
        ├─▶ Docker: docker stop realtime-worker-{meeting_id}
        └─▶ K8s: Delete Job realtime-worker-{meeting_id}
```

### 6.5 VAD 통합

클라이언트 VAD (Voice Activity Detection)와 Worker STT의 통합:

```
Client (useLiveKit.ts)
      │
      └─▶ @ricky0123/vad-web (Silero VAD)
              │
              └─▶ speech_start / speech_end 이벤트
                      │
                      └─▶ DataPacket → LiveKit Room
                              │
                              └─▶ Worker receives via on_data_received
                                      │
                                      └─▶ stt_client.mark_end_of_speech()
                                              │
                                              └─▶ Clova gRPC: epFlag=true
                                                      │
                                                      └─▶ Final Transcript 발행
```

### 6.6 Silence Filtering

불필요한 오디오 데이터 필터링:

```python
# RMS (Root Mean Square) 에너지 계산
def calculate_rms(audio_chunk: bytes) -> float:
    samples = np.frombuffer(audio_chunk, dtype=np.int16)
    return np.sqrt(np.mean(samples.astype(np.float32) ** 2))

# 임계값 이하 오디오 스킵
if calculate_rms(chunk) < SILENCE_THRESHOLD:
    continue  # STT에 전송하지 않음
```

**설정값**: `SILENCE_THRESHOLD = 300.0` (기본값)

### 6.7 환경 설정

```bash
# LiveKit
LIVEKIT_WS_URL=wss://livekit.example.com
LIVEKIT_API_KEY=xxx
LIVEKIT_API_SECRET=xxx

# Clova Speech STT
CLOVA_STT_ENDPOINT=clovaspeech-gw.ncloud.com:50051
CLOVA_STT_SECRET=xxx

# Backend API
BACKEND_API_URL=http://backend:8000
BACKEND_API_KEY=xxx

# Worker
MEETING_ID=meeting-uuid  # Worker Manager가 주입
```

### 6.8 K8s 리소스 설정

```yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

**Job 설정**:
- `ttl_seconds_after_finished`: 300 (완료 후 5분 후 정리)
- `backoff_limit`: 0 (재시도 없음)

---

## 부록: 디렉토리 구조

```
backend/app/
├── infrastructure/
│   └── graph/
│       ├── config.py                                    # MAX_RETRY 설정
│       ├── integration/
│       │   └── llm.py                                   # LLM 인스턴스
│       ├── schema/
│       │   └── models.py                                # ActionItemData, ActionItemEvalResult
│       └── workflows/
│           ├── generate_pr/
│           │   ├── state.py                            # GeneratePrState
│           │   ├── connect.py                          # 그래프 빌더
│           │   ├── graph.py                            # 컴파일된 그래프 인스턴스
│           │   └── nodes/
│           │       ├── extraction.py                   # extract_agendas
│           │       └── persistence.py                  # save_to_kg
│           └── mit_action/
│               ├── state.py                            # MitActionState
│               ├── connect.py                          # 그래프 빌더 (순환형)
│               ├── graph.py                            # 컴파일된 그래프 인스턴스
│               └── nodes/
│                   ├── extraction.py                   # extract_actions
│                   ├── evaluation.py                   # evaluate_actions
│                   ├── routing.py                      # route_eval
│                   └── persistence.py                  # save_actions
├── workers/
│   └── arq_worker.py                                   # Worker 태스크 정의
├── repositories/
│   └── kg/
│       └── repository.py                               # KGRepository (Neo4j 접근)
└── core/
    └── neo4j.py                                        # Neo4j Driver
```

---

## 부록: 참고 자료

- [MitHub Agent Overview](../mithub-agent-overview.md): 에이전트 전체 비전 및 역할
- [MitHub LangGraph Architecture](../mithub-langgraph-architecture.md): 그래프 구조 및 설계 원칙
- [MitHub LangGraph Development Guideline](../mithub-langgraph-development-guideline.md): 워크플로우 개발 가이드
- [MitHub LangGraph Coding Convention](../mithub-langgraph-coding-convention.md): 코딩 규칙 및 네이밍
