# MitHub Context Engineering

> 목적: 다자간 실시간 회의에서 AI 에이전트의 컨텍스트 관리 전략을 정의한다.
> 대상: 에이전트 개발자
> 범위: L0/L1 메모리, 토픽 분할, 시맨틱 서치, 에이전트 호출 컨텍스트
> 관련 문서: [MitHub Agent Overview](./mithub-agent-overview.md), [MitHub LangGraph Architecture](./mithub-langgraph-architecture.md)

---

## 0. 현재 구현 상태 (2026-02)

### 0.1 구현 완료

| 모듈 | 파일 | 상태 | 설명 |
|------|------|------|------|
| **ContextManager** | `backend/app/infrastructure/context/manager.py` | 완료 | L0/L1 메모리, L1 백그라운드 처리, L1 토픽 분할 |
| **ContextBuilder** | `backend/app/infrastructure/context/builder.py` | 완료 | 호출 유형별 컨텍스트 조합 + 시맨틱 서치 |
| **SpeakerContext** | `backend/app/infrastructure/context/speaker_context.py` | 완료 | 화자별 통계 및 역할 추론 |
| **In-memory Embedding** | `backend/app/infrastructure/context/embedding.py` | 완료 | BGE-M3 임베딩 생성/검색 |
| **토픽 분할 프롬프트** | `backend/app/infrastructure/context/prompts/topic_separation.py` | 완료 | 초기/재귀 토픽 분할 |
| **테스트 스크립트** | `backend/app/infrastructure/context/run_test.py` | 완료 | 옵션7 전용 통합 테스트 |
| **Checkpointer(그래프)** | `backend/app/infrastructure/graph/checkpointer.py` | 완료 | 멀티턴 그래프 상태 영속화 |
| **Context Runtime Cache** | `backend/app/services/context_runtime.py` | 완료 | 실시간 ContextManager 캐시/증분 업데이트 |

### 0.2 미구현/제약

| 기능 | 상태 | 설명 |
|------|------|------|
| **DB 영속화(L0/L1)** | 미구현 | transcripts는 SSOT. L0/L1은 메모리 기반, 재로드 시 재생성 |
| **Structured Output 강제** | 제한 | HCX-003은 JSON Schema 강제 불가 (프롬프트/파서 보정으로 안정화) |
| **토픽 병합 자동화** | 완료 | max_topics(30) 초과 시 유사 토픽 자동 병합 (cosine similarity > 0.80) |

---

## 1. First Principles

### 1.1 컨텍스트 정의
- **L0(최근 발화)**: 즉시 반응에 필요한 최신 맥락
- **L1(토픽 요약)**: 회의 전체 흐름/결정 요약
- **참여자/역할**: 다자간 회의에서 중요한 메타 정보

### 1.2 제약 조건 (HCX-003 기준)
- 컨텍스트 윈도우: 8K 토큰
- 모든 transcript를 넣을 수 없음 → **선별적 압축 필수**

---

## 2. L0/L1 메모리 구조 (현재 구현)

### 2.1 L0
- `l0_buffer`: 최근 발화 25턴 고정 deque
- `l0_topic_buffer`: 토픽 버퍼 (최대 100턴 제한)
- 발화마다 `add_utterance()`로 추가

### 2.2 L1
- **턴 기반 트리거**: `l1_update_turn_threshold` (기본 25)
- 25턴 도달 시 **L1 청크 큐잉** → 백그라운드 요약
- 토픽 분할은 LLM 기반, 결과는 `TopicSegment` 리스트로 저장

### 2.3 DB 역할
- **transcripts가 SSOT**
- 실서비스는 **Context Runtime Cache**에서 증분 업데이트
- L0/L1은 메모리 기반, 재시작 시 DB로부터 재구성 가능

---

## 3. 토픽 분할 및 L1 처리

### 3.1 토픽 분할 방식
- `TOPIC_SEPARATION_PROMPT`: 첫 25턴
- `RECURSIVE_TOPIC_SEPARATION_PROMPT`: 이후 청크 + 기존 토픽 요약
- JSON-only 출력 요구 + 요약 1문장/120자 제한

### 3.2 파싱 안정화
- `_safe_json_loads()`에서 코드펜스 제거 및 부분 JSON 파싱
- 파싱 실패 시 fallback 세그먼트 생성 (`Topic_{start}_{end}`)
- 타입 보정 로직 포함(정수/불리언/키워드)

### 3.3 백그라운드 처리
- `_pending_l1_chunks` 큐에 청크 저장
- `_schedule_background_l1()` → `_run_l1_background()`에서 순차 처리
- `await_l1_idle()`로 에이전트 호출 전에 L1 완료 보장

---

## 4. 인메모리 임베딩 & 시맨틱 서치

### 4.1 임베딩
- 모델: BGE-M3 (`BAAI/bge-m3`)
- 요약(`segment.summary`)에 대해 임베딩 생성 후 메모리에 저장

### 4.2 검색
- `search_similar_topics(query, top_k, threshold)`
- 임베딩 미사용 시 fallback으로 최근 L1 반환

### 4.3 토픽 병합
- 토픽 수가 `max_topics`(기본 30) 초과 시 자동 병합
- `_check_and_merge_topics()`: L1 처리 완료 후 자동 호출
- 유사도 계산: cosine similarity (임베딩 기반)
- 병합 조건: `topic_merge_threshold`(기본 0.80) 이상
- LLM으로 병합 요약 생성, 실패 시 단순 병합 fallback

---

## 5. 에이전트 호출 시 컨텍스트 주입 (실시간 캐시 기준)

### 5.1 흐름
1. Worker가 transcript 저장 직후 `/agent/meeting/call` 호출
2. API가 **Context Runtime Cache**를 증분 업데이트
3. 에이전트 호출 시 캐시된 ContextManager 사용
4. L1 완료 대기 (`await_l1_idle()`)
5. Planning context 생성 (L0/L1 요약)
6. Planning 단계에서 `required_topics` 도출
7. `additional_context` 생성 후 그래프 실행

### 5.2 참고
- `required_topics`는 **그래프 외부에서 사용**, 오케스트레이션 상태에는 전달하지 않음

### 5.3 실제 서비스 워크플로우 (RealtimeWorker ↔ API)

```
┌──────────────┐        ┌────────────────────┐        ┌─────────────────────────────┐
│ LiveKit/STT  │  --->  │ RealtimeWorker     │  --->  │ Backend API                 │
└──────────────┘        │ (backend/worker)   │        │ (FastAPI)                   │
                        └────────────────────┘        └─────────────────────────────┘
                                │                                 │
                                │ 1) transcript 저장 요청          │
                                ├────────────────────────────────► │ /transcripts
                                │                                 │
                                │ 2) 저장 결과 id 수신             │
                                ◄─────────────────────────────────┤
                                │                                 │
                                │ 3) /agent/meeting/call 호출      │
                                ├────────────────────────────────► │ update_agent_context
                                │                                 │  - context_runtime 증분 업데이트
                                │                                 │  - ContextManager.add_utterance
                                │                                 │  - L1 백그라운드 큐잉
                                │                                 │
                                │ 4) wake word 감지 시 /agent/meeting 호출
                                ├────────────────────────────────► │ run_agent_with_context
                                │                                 │  - 캐시된 ContextManager 사용
                                │                                 │  - await_l1_idle()
                                │                                 │  - planning → additional_context → graph
                                │                                 │
                                │ 5) 응답 스트리밍                 │
                                ◄─────────────────────────────────┤
```

#### 주요 코드 경로
- Worker 실시간 업데이트: `backend/worker/src/main.py`
  - transcript 저장 직후 `_update_context_realtime()` 호출
- Context 캐시/증분 처리: `backend/app/services/context_runtime.py`
  - meeting_id별 ContextManager 캐시
  - `last_processed_start_ms` 기준 증분 조회
- API 엔드포인트:
  - `/agent/meeting/call`: `backend/app/api/v1/endpoints/agent.py`
  - `/agent/meeting`: `backend/app/api/v1/endpoints/agent.py`

---

## 6. run_test.py (통합 파이프라인 검증)

run_test.py는 **실제 서비스와 동일한 전체 컨텍스트 파이프라인**을 단일 스크립트로 검증한다.

### 6.1 검증 범위

| 검증 항목 | 설명 |
|----------|------|
| **DB 연동** | 임시 SQLite DB에 발화를 순차 삽입 (실제 transcripts 테이블 시뮬레이션) |
| **L0 업데이트** | 매 발화마다 `add_utterance()` 호출, 최근 25턴 유지 확인 |
| **L1 백그라운드 처리** | 25턴 도달 시 자동 큐잉 → 백그라운드 토픽 분할/요약 |
| **시맨틱 서치** | BGE-M3 임베딩 기반 유사 토픽 검색 |
| **토픽 병합** | max_topics 초과 시 유사 토픽 자동 병합 |
| **Checkpointer** | 그래프 상태 영속화 (SQLite 기반) |

### 6.2 실행 흐름

```
1. 임시 DB 초기화 (SQLite)
2. 샘플 발화 50개 순차 삽입 (0.5초 간격)
   └── 매 발화마다 ContextManager.add_utterance()
3. 25턴 도달 시 [L1 BG START] 로그 출력
   └── 백그라운드에서 토픽 분할/요약 수행
4. 모든 발화 완료 후 await_pending_l1() 호출
   └── 백그라운드 작업 완료 대기
5. 에이전트 쿼리로 시맨틱 토픽 검색 수행
6. Checkpointer 저장 여부 확인
```

### 6.3 실행 방법

```bash
cd backend
uv run python -m app.infrastructure.context.run_test
```

### 6.4 예상 출력

```
[L1 BG START] 토픽 분할 시작
[L1 BG DONE] 토픽 2개 생성

=== Topic Search (Agent Query) ===
Query: "예산 관련 논의 내용을 알려줘"
Found 2 topics:
  - 예산 논의 (similarity: 0.85)
  - 분기 계획 (similarity: 0.72)

✅ 체크포인트 저장됨!
```

---

## 7. 주요 설정값 (ContextConfig)

```python
l0_max_turns = 25
l0_max_tokens = 3000
l0_topic_buffer_max_turns = 100
l0_topic_buffer_max_tokens = 10000

l1_update_turn_threshold = 25

speaker_buffer_max_per_speaker = 25

max_topics = 30

embedding_model = "BAAI/bge-m3"
embedding_dimension = 1024

topic_search_top_k = 5
topic_search_threshold = 0.30
```

---

## 8. Known Issues

| 이슈 | 원인 | 현 상태 |
|------|------|---------|
| JSON 깨짐 | HCX-003 구조화 출력 미지원 | 프롬프트 강화 + 파서 보정으로 완화 |
| 토픽 섞임 | 토픽 전환 감지 없음 | 25턴 배치 기준으로만 분리 |
| L1 영속화 없음 | 메모리 기반 | 재로드 시 L1 재생성 필요 |
| 임베딩 의존성 | FlagEmbedding 설치 필요 | 미설치 시 fallback |
| 실시간 캐시 유실 | 서버 재시작 시 캐시 초기화 | 재시작 후 DB 재적재 필요 |

---

## 9. 구현 파일 맵

```
backend/app/infrastructure/context/
├── __init__.py
├── config.py
├── models.py
├── manager.py          # L0/L1 메모리, 백그라운드 L1, 임베딩/검색, 토픽 병합
├── builder.py          # 호출 유형별 컨텍스트 조합
├── embedding.py        # BGE-M3 임베딩
├── speaker_context.py  # 화자별 통계
├── run_test.py         # 옵션7 전용 통합 테스트
└── prompts/
    ├── __init__.py
    ├── topic_separation.py   # 초기/재귀 토픽 분할
    └── topic_merging.py      # 유사 토픽 병합 프롬프트

backend/app/services/
└── context_runtime.py  # 실시간 ContextManager 캐시/증분 업데이트

backend/app/api/v1/endpoints/
└── agent.py            # /agent/meeting/call, /agent/meeting
```

---

## 10. 요약

- **L0/L1 메모리 구조**는 25턴 배치 기반으로 안정적 운용
- **LLM 토픽 분할 + 파서 보정**으로 JSON 실패율 최소화
- **임베딩 기반 시맨틱 서치**는 인메모리로 제공
- **checkpointer는 그래프 상태 영속화**에만 사용, 컨텍스트는 별개
