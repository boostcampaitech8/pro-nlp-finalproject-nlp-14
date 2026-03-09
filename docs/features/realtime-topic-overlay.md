# 실시간 회의 토픽 사이드바 (SSE + Redis Pub/Sub)

## 목적

미팅룸에서 Context Engineering L1 토픽을 에이전트 호출 없이 실시간으로 보여준다.

- 25발화 단위로 L1 토픽 생성/갱신
- 최신 토픽이 상단 정렬
- SSE push 기반으로 주기적 GET 최소화
- 미팅 화면 좌측 고정 사이드바 + 토픽 클릭 시 인라인 상세 카드

---

## 현재 구현 상태 (2026-02-03)

- [x] 토픽 snapshot API (`GET /context/topics`)
- [x] 토픽 SSE API (`GET /context/topics/stream`)
- [x] Redis Pub/Sub 기반 update broadcast
- [x] transcript 저장 시 ContextRuntime 동기화 + publish
- [x] 프론트 EventSource 구독 훅 + 재연결 로직
- [x] 미팅룸 좌측 `TopicSidebar` 렌더링
- [x] 토픽 클릭 시 토픽 아래 상세 카드(slide/fade) 노출

---

## 아키텍처

```text
[Realtime STT Worker]
        |
        | POST /api/v1/meetings/{meeting_id}/transcripts
        v
[TranscriptService.create_transcript]
        |
        | _sync_to_context_runtime() (runtime.lock)
        | - manager.add_utterance()
        | - L1/pending 변화 감지
        v
[publish_topic_update] ---> Redis Pub/Sub (meeting:topics:{meeting_id})
                                |
                                v
                   [SSE /context/topics/stream]
                                |
                                | init/update/heartbeat
                                v
             [useMeetingTopics(EventSource, reconnect)]
                                |
                                v
                [MeetingRoom + TopicSidebar(좌측 고정)]
```

참고:
- 실시간 push는 Redis Pub/Sub 경로를 사용한다.
- ARQ는 본 스트리밍 경로의 필수 구성요소는 아니다.

---

## 데이터 흐름

1. Worker가 발화를 `POST /meetings/{meeting_id}/transcripts`로 저장한다.
2. `TranscriptService._sync_to_context_runtime()`가 활성 runtime에 발화를 즉시 반영한다.
3. 25발화 기준으로 L1 chunk가 큐잉/처리된다.
4. 토픽 개수 또는 pending chunk 수가 바뀌면 Redis에 update를 발행한다.
5. 신규 chunk가 큐잉되면 L1 완료 시점에 최신 상태를 1회 추가 발행한다.
6. SSE endpoint가 Redis 메시지를 `update` 이벤트로 push한다.
7. 프론트 `useMeetingTopics`가 state를 갱신하고 `TopicSidebar`가 즉시 재렌더링된다.

재입장 보정:
- snapshot/SSE init 생성 시 pending L1이 있으면 `await_l1_idle()` 이후 응답해,
  재입장 직후에도 최신 토픽 누락을 줄인다.

---

## API 명세

### 1) Snapshot 조회

`GET /api/v1/meetings/{meeting_id}/context/topics`

- 인증: `Authorization: Bearer <token>`
- 권한: 회의 참여자만 접근 (`require_meeting_participant`)
- 용도: 단발 조회, 폴백, 디버깅

### 2) SSE 스트리밍

`GET /api/v1/meetings/{meeting_id}/context/topics/stream?token=<JWT>`

- 인증: query token (`EventSource`는 Authorization header 미지원)
- 권한: `require_meeting_participant_sse`
- 이벤트 타입:
  - `init`: 연결 직후 snapshot 1회
  - `update`: Redis publish 시점
  - `heartbeat`: keep-alive

payload (`TopicFeedResponse`, camelCase):

```json
{
  "meetingId": "550e8400-e29b-41d4-a716-446655440000",
  "pendingChunks": 1,
  "isL1Running": true,
  "currentTopic": "레이턴시 실험 계획",
  "topics": [
    {
      "id": "topic-uuid-1",
      "name": "레이턴시 측정 방법론",
      "summary": "WebRTC 기반 실시간 음성 전송의 레이턴시 측정 논의",
      "startTurn": 26,
      "endTurn": 50,
      "keywords": ["레이턴시", "WebRTC", "측정"]
    }
  ],
  "updatedAt": "2026-02-03T00:00:00+00:00"
}
```

---

## 프론트 UI 규칙 (현재)

### 배치
- `MeetingRoom` 메인 레이아웃에서 좌측 고정 사이드바로 렌더링
- 너비는 채팅 패널과 동일 (`w-80`)

### 리스트 표시
- 최신 토픽이 위(`endTurn` 내림차순)
- 상태 불릿:
  - active: 초록색 채움
  - non-active: 빈 원형
- active 판정: 최근 25턴 윈도우와 토픽 구간이 겹치면 active

### 상세 표시
- 호버가 아니라 클릭으로 상세 카드 토글
- 상세 카드는 해당 토픽 항목 바로 아래에 표시
- `summary`, `keywords` 노출
- `max-height + opacity + translate` 애니메이션으로 slide/fade 적용

---

## 레거시 정리 내역

### 프론트
- 중앙 상단 `TopicOverlay` 기반 설명/참조 제거
- 토픽 상세를 `fixed` 툴팁 패널로 띄우던 방식 제거
- `useMeetingTopics`의 미사용 반환값(`currentTopic`, `isLoading`, `isConnected`, `error`, `refresh`) 정리

### 문서
- 오버레이 중심 설명을 사이드바 중심 설명으로 전면 교체
- 관련 파일 목록에서 `TopicOverlay.tsx` 제거, `TopicSidebar.tsx` 반영

---

## 테스트 가이드

### SSE 확인

```bash
curl -N "http://localhost:8000/api/v1/meetings/{meeting_id}/context/topics/stream?token=${TOKEN}"
```

### Snapshot 확인

```bash
curl -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:8000/api/v1/meetings/{meeting_id}/context/topics"
```

### UI 시나리오

1. 미팅룸 입장 후 25개 이상 발화 입력
2. 사이드바에 토픽 생성/정렬 확인
3. 토픽 클릭 시 해당 항목 하단 상세 카드 노출 확인
4. 다른 토픽 클릭 시 상세 카드가 대상 항목으로 이동하는지 확인
5. 재입장 직후 기존 토픽이 즉시 보이는지 확인

---

## 관련 파일

- `backend/app/schemas/context.py`
- `backend/app/core/topic_pubsub.py`
- `backend/app/api/v1/endpoints/context.py`
- `backend/app/api/dependencies.py`
- `backend/app/services/transcript_service.py`
- `backend/app/services/context_runtime.py`
- `backend/app/api/v1/router.py`
- `frontend/src/types/context.ts`
- `frontend/src/types/index.ts`
- `frontend/src/services/meetingTopicService.ts`
- `frontend/src/hooks/useMeetingTopics.ts`
- `frontend/src/components/meeting/TopicSidebar.tsx`
- `frontend/src/components/meeting/MeetingRoom.tsx`
