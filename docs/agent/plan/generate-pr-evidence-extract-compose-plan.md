# Generate PR Evidence/Extract/Compose 구현 문서 (최신)

> **문서 버전**: 2026-02-05
> **프롬프트 버전**: 1.5.0
> **주요 변경**: LLM 기반 아젠다 병합 도입

이 문서는 `generate_pr` 워크플로우가 현재 코드에서 어떻게 동작하는지, 그리고 사용자에게 어떤 경험을 제공하는지를 설명한다.
코드 조각 대신 구현 의도와 실제 동작을 중심으로 정리한다.

---

## 1) 한눈에 보는 현재 구조

- 그래프 흐름: `router -> (single_pass | chunked_pass) -> hard_gate -> saver`
- 라우팅 기준:
  - `short`: 토큰 `< 5000` 이고 실시간 토픽 수 `<= 7`
  - `long`: 위 조건을 만족하지 않으면 모두 long
- 모델:
  - PR 추출/요약 정제: **HCX-007** (`get_pr_generator_llm`)
  - 실시간 토픽 생성(별도 컨텍스트 런타임): **HCX-DASH-002**
- long 경로는 고정 3청크(50% overlap) 추출 후 병합
- Evidence는 `SpanRef(start_utt_id/end_utt_id)` 중심으로 저장/검증/표시

---

## 2) 왜 이렇게 설계했는가 (First Principles)

핵심 문제는 3가지다.

1. 긴 회의록에서 정보 손실 없이 처리할 수 있는가?
2. 생성된 아젠다/결정이 원문에 근거하는지 검증 가능한가?
3. 사용자에게 "어디서 나온 내용인지" 즉시 보여줄 수 있는가?

현재 구현은 아래 원칙을 따른다.

- 길이 문제: 전체 1회 처리 대신 `3청크 + overlap`으로 문맥 손실 완화
- 환각 문제: Hard Gate에서 evidence의 utterance ID 실존 여부 강제
- 신뢰성 문제: 회의록 UI에서 SpanRef를 클릭해 원문 발화 직접 확인

---

## 3) 데이터 계약 (입력/출력)

### 입력

- `generate_pr_meeting_id`
- `generate_pr_transcript_text`
- `generate_pr_transcript_utterances`
  - 각 발화는 `id, speaker_name, text, start_ms, end_ms`
- `generate_pr_realtime_topics`
  - 실시간 L1 토픽 스냅샷

### 중간 상태

- `generate_pr_route` (`short | long`)
- `generate_pr_chunks` (청크 메타 정보)
- `generate_pr_agendas` (evidence 포함 아젠다/결정)
- `generate_pr_summary`

### 출력

- `generate_pr_agenda_ids`
- `generate_pr_decision_ids`

---

## 4) SpanRef 표준 (현재 구현)

SpanRef는 아래 필드로 구성된다.

- 필수: `transcript_id`, `start_utt_id`, `end_utt_id`
- 선택: `sub_start`, `sub_end`, `start_ms`, `end_ms`, `topic_id`, `topic_name`

의미:

- 주소 체계의 1차 앵커는 `utterance id`
- `sub_*`와 `ms`는 보조 정보
- `topic_*`는 병합/UX 보조 힌트

중요:

- Neo4j에는 별도 evidence edge를 만들지 않고, 현재는 `Agenda.evidence`, `Decision.evidence` 속성(JSON)으로 저장한다.

---

## 5) 경로별 실행 방식

### 5.1 short 경로 (`extract_single`)

- 전체 발화를 1회 추출
- LLM이 evidence를 비우면 청크 전체 span으로 fallback 가능(단일 경로만)
- 결과를 그대로 Hard Gate로 전달

장점:

- 호출 수가 적어 빠름

주의:

- 단일 호출 특성상 특정 케이스에서 evidence 범위가 넓어질 수 있음

### 5.2 long 경로 (`extract_chunked`)

long 경로는 아래 순서로 동작한다.

1. 발화를 고정 3청크로 분할 (각 청크 크기 = 전체의 50%, 인접 청크 50% overlap)
2. 각 청크에 해당하는 실시간 토픽 컨텍스트를 프롬프트에 주입
3. 청크별 Agenda/Decision 추출
4. LLM 기반 아젠다 병합 (의미적 중복 판단)
5. 청크 요약들을 다시 1회 LLM으로 정제해 최종 요약 생성

LLM 호출 수:

- 청크 추출 3회 + 아젠다 병합 1회 + 요약 정제 1회 = 총 5회

---

## 6) 병합 전략 (현재 코드 기준)

병합은 LLM 기반으로 동작하며, 실패 시 규칙 기반으로 fallback한다.

### 6.1 LLM 기반 병합 (`_merge_chunk_results_with_llm`)

1. 모든 청크의 agenda를 `agenda_id`로 식별하여 후보 목록 생성
2. LLM에게 의미적으로 중복되는 agenda를 그룹으로 묶도록 요청 (`AGENDA_MERGE_PROMPT`)
3. LLM이 `source_agenda_ids`, `merged_topic`, `merged_description`, `merged_decision_*` 반환
4. 병합 시 evidence는 union 방식으로 보존 (LLM이 evidence를 생성/수정하지 않음)
5. LLM 출력에서 누락된 agenda는 singleton으로 추가
6. 최종 결과는 시간순 정렬

### 6.2 규칙 기반 병합 (fallback)

LLM 병합 실패 시 규칙 기반으로 fallback:

1. evidence의 `topic_id`(또는 fallback 추정)로 그룹핑
2. 같은 그룹 안에서만 병합 후보를 비교
3. 아래 둘 중 하나를 만족하면 병합:
   - Evidence overlap >= 50%
   - Topic 키워드 유사도 >= 50%
4. evidence는 union 방식으로 보존

### 의도

- 의미적 유사성은 LLM이 판단 (표현이 다른 유사 아젠다도 병합 가능)
- 근거(evidence)는 절대 잃지 않도록 코드에서 union 처리
- LLM 실패에도 안정적으로 동작하도록 fallback 보장

---

## 7) Hard Gate (최소 근거 검증)

Hard Gate는 저장 직전 최종 필터다.

- agenda evidence의 `start_utt_id/end_utt_id`가 실제 입력 발화 ID에 존재해야 함
- decision evidence도 동일 검증
- decision evidence가 비면 agenda evidence로 1회 fallback
- agenda와 decision 모두 evidence가 없으면 해당 agenda 제거

결과:

- "근거 없는 항목"이 저장 단계로 넘어가는 것을 최소화

---

## 8) Rate Limit 대응 (429 완화)

long 경로에서 청크 호출 실패를 줄이기 위해 다음을 적용했다.

- 청크 호출 간 고정 지연: 1.5초
- 청크별 최대 재시도: 3회
- 429 감지 시 지수 백오프: 4s -> 8s -> 16s (최대 20s 캡)
- 기타 예외는 짧은 선형 백오프로 재시도

효과:

- 일부 청크만 실패해서 결과가 편향되는 상황을 줄임

---

## 9) 저장 방식 (Neo4j)

저장 노드는 `create_minutes`를 통해 아래를 1회에 처리한다.

- Meeting summary 업데이트
- Agenda 생성 및 순서 관계(`CONTAINS`) 연결
- Decision 생성 및 관계(`HAS_DECISION`, `DECIDED_IN`) 연결
- evidence는 Agenda/Decision 속성에 JSON 문자열로 직렬화 저장

현재 범위:

- Evidence를 위한 별도 노드/엣지(`HAS_EVIDENCE` 등)는 아직 없음

---

## 10) 사용자 경험 (회의록 화면의 SpanRef 확인)

프론트엔드에서 구현된 동작:

- 아젠다 헤더 오른쪽에 `근거 보기 (N)` 버튼 표시
  - `N`은 해당 아젠다 + 하위 결정들의 SpanRef를 합친 실제 개수
  - 근거가 없으면 버튼 자체를 숨김
- 버튼 클릭 시:
  - 우측 패널이 열리고, 좌측 회의록 영역이 좁아진 2열 레이아웃으로 전환
  - 같은 버튼을 다시 누르면 패널 닫힘(토글)
- 우측 패널:
  - 선택된 아젠다 제목, SpanRef 개수 표시
  - 각 SpanRef에 대해 연결된 원문 발화 목록 표시
  - 매칭 실패 시 `"원문 발화를 찾지 못했습니다."` 안내
- 원문 매칭 우선순위:
  1) utterance id 정확 매칭
  2) turn-like id fallback
  3) 시간(ms) 범위 fallback

---

## 11) 운영 로그 해석 가이드

대표 로그와 의미:

- `generate_pr route selected ...`
  - short/long 라우팅 결과 및 기준값
- `Three-chunk extraction ...`
  - long 경로 진입 확인
- `Chunk evidence extraction ...`
  - 각 청크에서 evidence가 붙은 agenda/decision 수
- `Chunk extraction rate-limited ...`
  - 429로 인한 백오프 동작
- `LLM merge finished: input=X, output=Y`
  - LLM 병합 결과 (input: 청크에서 추출된 총 agenda 수, output: 병합 후 agenda 수)
- `LLM merge failed, fallback to rule merge: ...`
  - LLM 병합 실패로 규칙 기반 fallback 동작
- `Hard Gate finished: input=X, passed=Y`
  - 최종 통과율 확인

---

## 12) 현재 알려진 리스크/제약

1. Evidence를 Neo4j 속성(JSON)으로만 저장하고 있어, 그래프 탐색 관점의 정밀한 evidence 질의는 제한적이다.
2. LLM 병합이 실패하면 규칙 기반 fallback으로 동작하며, 이 경우 표현이 다른 유사 아젠다가 분리될 수 있다.
3. long 경로는 LLM 5회 호출로 비용이 증가한다 (청크 3 + 병합 1 + 요약 1).
4. 라우팅 기준(`3000 tokens`, `topics > 3`)은 고정값이라 도메인별 최적점이 다를 수 있다.
5. short 경로 fallback evidence는 보수적 안전장치지만, 근거 범위가 넓어질 가능성은 남아 있다.

---

## 13) 결론

현재 구현은 다음 목표를 이미 충족한다.

- 긴 회의를 안정적으로 처리하는 2경로 구조
- SpanRef 기반 근거 추출/검증/표시의 end-to-end 연결
- LLM 기반 의미적 병합으로 중복 아젠다 통합
- rate limit 상황에서의 실전 완화 로직
- 사용자 입장에서 "근거를 클릭해 원문 확인" 가능한 UX

즉, 이 시스템은 지금 기준에서 "추출 품질 + 근거 신뢰 + 사용자 검증 가능성"의 균형을 맞춘 상태이며, 이후 개선은 evidence 저장 구조(속성 -> 그래프 관계) 고도화와 extraction 프롬프트 정교화가 핵심이다.
