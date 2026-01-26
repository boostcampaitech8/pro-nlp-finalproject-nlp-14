# Architecture Decisions - Backend

**Last Updated**: 2026-01-26

---

## ADR-001: Shared API Dependencies Module

**Date**: 2026-01-08
**Status**: Accepted

### Context
6개 endpoint 파일에서 동일한 인증/권한 체크 코드가 180+ lines 중복되고 있었음.

### Decision
`app/api/dependencies.py` 모듈을 생성하여 공통 dependency 함수 중앙화.

### Consequences
**Positive**:
- 180+ lines 중복 제거
- 권한 로직 변경 시 한 곳만 수정
- 테스트 시 dependency override 용이

**Negative**:
- 새로운 의존성 추가 (모든 endpoint가 dependencies.py 의존)

---

## ADR-002: Strategy Pattern for WebSocket Handlers

**Date**: 2026-01-08
**Status**: Accepted (Pattern applicable to LiveKit webhooks)

### Context
`webrtc.py`의 `handle_websocket_messages()` 함수가 11개 분기의 if-elif 체인으로 구성되어 있었음. 새 메시지 타입 추가 시 함수 수정 필요 (Open/Closed Principle 위반).

### Decision
Strategy Pattern 적용:
- `MessageHandler` Protocol 정의
- 메시지 타입별 Handler 클래스 생성
- Handler Registry 방식으로 디스패치

### Consequences
**Positive**:
- 새 메시지 타입 추가가 클래스 추가 + 등록으로 간단해짐
- 각 핸들러 독립적 테스트 가능
- 50줄 if-elif → 10줄 dispatch로 단순화

**Negative**:
- 클래스 수 증가 (6개 핸들러 클래스)
- 새 파일 추가 필요

### Alternatives Considered
1. **Command Pattern**: 더 무거움, 현재 요구사항에 과함
2. **Dictionary Dispatch**: 타입 안전성 부족

---

## ADR-004: Service Layer for Recordings

**Date**: 2026-01-08
**Status**: Accepted

### Context
`recordings.py` endpoint 파일에 비즈니스 로직이 직접 포함되어 있어:
- HTTP 레이어와 비즈니스 로직이 혼재
- 단위 테스트 시 HTTP 레이어 필요
- 570줄의 큰 파일

### Decision
`RecordingService` 클래스로 비즈니스 로직 추출:
- File validation
- Presigned URL 생성
- Recording 상태 관리
- DB 조회/저장

### Consequences
**Positive**:
- recordings.py 570 → 324줄 감소
- 비즈니스 로직 단위 테스트 가능
- Endpoint는 HTTP 처리만 담당

**Negative**:
- 서비스 클래스 추가
- Endpoint와 Service 간 데이터 변환 필요

---

## ADR-005: ICE Candidate Parser Utility

**Date**: 2026-01-08
**Status**: Accepted

### Context
`RecordingSession._parse_ice_candidate()` 메서드가 64줄의 복잡한 문자열 파싱 로직을 포함. 테스트가 어렵고 재사용 불가.

### Decision
`app/utils/ice_parser.py`에 `ICECandidateParser` 클래스로 추출.

### Consequences
**Positive**:
- 파싱 로직 독립적 테스트 가능
- 다른 곳에서 재사용 가능
- RecordingSession 단순화

**Negative**:
- 새 파일 추가
- Import 추가

---

## ADR-006: Constants Centralization

**Date**: 2026-01-08
**Status**: Accepted

### Context
매직 넘버들이 코드 전체에 흩어져 있음:
- `500 * 1024 * 1024` (파일 크기)
- `3600` (URL 만료)
- 등

### Decision
`app/core/constants.py`에 모든 상수 중앙화.

### Consequences
**Positive**:
- 설정 변경 시 한 곳만 수정
- 코드 가독성 향상
- 상수 의미 명확화

**Negative**:
- 새 import 필요

---

## ADR-008: STT Provider Abstraction

**Date**: 2026-01-10
**Status**: Accepted

### Context
회의 녹음 파일을 STT로 변환하는 기능이 필요. OpenAI Whisper를 사용하되, 향후 자체 호스팅 모델이나 로컬 모델로 교체 가능해야 함.

### Decision
Provider Pattern 적용:
- `STTProvider` ABC 정의 (추상 클래스)
- `OpenAIWhisperProvider` 구현체
- `STTProviderFactory`로 Provider 생성

### Consequences
**Positive**:
- 외부 서비스 교체 용이 (OpenAI → Local Whisper → Self-hosted)
- 테스트 시 Mock Provider 주입 가능
- 설정으로 Provider 선택 가능

**Negative**:
- 추상화 레이어 추가
- 초기 구현 복잡도 증가

---

## ADR-009: ARQ Worker for Async STT Processing

**Date**: 2026-01-10
**Status**: Accepted

### Context
STT 변환은 수십 초 ~ 수 분 소요되는 작업. 동기 처리 시 HTTP 타임아웃 발생. 비동기 작업 큐 필요.

### Decision
ARQ (Async Redis Queue) 사용:
- Redis 기반 경량 작업 큐
- Python asyncio 네이티브 지원
- 재시도, 타임아웃 지원

### Consequences
**Positive**:
- HTTP 요청과 STT 처리 분리
- 작업 실패 시 자동 재시도
- Worker 수평 확장 가능

**Negative**:
- Redis 의존성 추가
- Worker 프로세스 별도 운영 필요
- 작업 상태 조회 별도 구현 필요

### Alternatives Considered
1. **Celery**: 더 무거움, 현재 규모에 과함
2. **RQ (Redis Queue)**: asyncio 미지원
3. **Dramatiq**: 좋은 대안이지만 ARQ가 더 경량

---

## ADR-010: VAD Preprocessing for STT Cost Optimization

**Date**: 2026-01-10
**Status**: Accepted

### Context
회의 녹음에는 무음 구간이 많음. 전체 파일을 STT 처리하면 비용과 시간 낭비.

### Decision
VAD (Voice Activity Detection) 전처리:
- webrtcvad 라이브러리 사용
- 발화 구간만 추출 후 STT 처리
- 각 구간 타임스탬프 보존

### Consequences
**Positive**:
- STT API 호출 횟수/시간 감소 (비용 절약)
- 정확도 향상 (무음 구간 제거)
- 발화 구간별 개별 처리 가능

**Negative**:
- 전처리 시간 추가
- FFmpeg 의존성 필요 (pydub)
- VAD 오탐지 시 발화 누락 가능

### Implementation Notes
- Dockerfile에 FFmpeg 설치 필수
- pydub로 오디오 포맷 변환
- 16kHz mono PCM으로 변환 후 VAD 적용

---

## ADR-012: Auto-Merge After Individual STT Completion

**Date**: 2026-01-13
**Status**: Accepted

### Context
녹음 업로드 완료 시 개별 `transcribe_recording_task`가 자동 실행되어 각 녹음의 STT는 완료되지만, `merge_utterances`가 호출되지 않아 통합 회의록이 생성되지 않음.

두 가지 STT 처리 경로가 존재:
1. **개별 처리** (자동): 녹음 업로드 -> `transcribe_recording_task` -> merge 없음
2. **일괄 처리** (수동): `/transcribe` 호출 -> `transcribe_meeting_task` -> merge 포함

### Decision
`transcribe_recording_task` 완료 후 자동 merge 로직 추가:
1. 개별 STT 완료 후 `check_all_recordings_processed()` 호출
2. 모든 녹음이 처리 완료(성공/실패)되면 `merge_utterances()` 자동 실행
3. STT 실패 시에도 다른 녹음이 모두 처리되었으면 병합 시도

### Consequences
**Positive**:
- 녹음 업로드만으로 자동 회의록 생성
- 사용자가 `/transcribe` 수동 호출 불필요
- 마지막 녹음 STT 완료 시점에 자동 병합

**Negative**:
- 동시 STT 완료 시 race condition 가능성 (실제로는 DB 트랜잭션으로 방지)

### Implementation
```python
# arq_worker.py transcribe_recording_task
async def transcribe_recording_task(ctx, recording_id, language="ko"):
    # ... STT 처리 ...
    await stt_service.complete_transcription(recording_uuid, result)

    # 모든 녹음 STT 완료 확인 후 자동 병합
    all_processed = await transcript_service.check_all_recordings_processed(meeting_id)
    if all_processed:
        await transcript_service.get_or_create_transcript(meeting_id)
        await transcript_service.merge_utterances(meeting_id)
```

**파일**: `backend/app/workers/arq_worker.py`

---

## ADR-013: Manual Trigger for generate_pr Workflow

**Date**: 2026-01-26
**Status**: Accepted (임시 - 자동화 조건 충족 시 제거)

### Context
STT 완료 후 자동으로 `generate_pr_task`를 트리거하는 로직에 다음 문제가 있음:

1. **트랜스크립트 완료 시점 불명확**: 녹음 파일이 뒤늦게 추가될 수 있어, "모든 녹음이 완료되었다"의 기준이 불명확
2. **Race Condition**: 여러 녹음의 STT가 동시에 완료되면 `generate_pr_task`가 중복 큐잉될 수 있음
3. **이벤트 순서 불확실**: LiveKit의 `room_finished` 이벤트와 `egress_ended` 이벤트 순서가 보장되지 않음

**문제 시나리오:**
```
1. 녹음 A 완료 → STT 완료 → check_all_recordings_processed() = True
2. generate_pr 실행 → 녹음 A만으로 요약 생성
3. 녹음 B가 뒤늦게 도착 → STT 완료
4. 녹음 B의 내용은 요약에 포함되지 않음!
```

### Decision
`generate_pr_task` 트리거를 자동에서 수동으로 변경:
- 자동 트리거 코드 제거 (`arq_worker.py`)
- 수동 트리거 API 추가 (`POST /meetings/{meeting_id}/generate-pr`)
- ARQ `_job_id`로 중복 실행 방지

### Consequences
**Positive**:
- Race condition 완전 제거
- 사용자가 원하는 시점에 PR 생성 가능
- 모든 녹음이 확실히 처리된 후 실행 보장

**Negative**:
- 사용자가 수동으로 API 호출 필요
- UX 단계 추가

### 자동화 복귀 조건 (이 ADR 제거 시점)
다음 조건이 모두 구현되면 자동 트리거로 복귀하고 이 ADR을 제거:

1. **회의 종료 상태 관리**: `room_finished` 이벤트에서 `Meeting.status`를 `COMPLETED`로 변경
2. **조건부 트리거**: `egress_ended` → STT 완료 시점에:
   - `Meeting.status == COMPLETED` (회의가 확실히 종료됨)
   - `check_all_recordings_processed() == True` (모든 녹음 처리 완료)
   - 두 조건 모두 만족 시에만 `generate_pr_task` 트리거
3. **중복 방지**: ARQ `_job_id` 또는 Redis 분산 락 적용

**관련 파일 수정 필요:**
- `livekit_webhooks.py`: `handle_room_finished`에서 회의 상태 변경 추가
- `arq_worker.py`: `transcribe_recording_task`에서 조건부 자동 트리거 복원

### API
```
POST /api/v1/meetings/{meeting_id}/generate-pr
Response: 202 Accepted
{
  "status": "queued",
  "meeting_id": "...",
  "job_id": "generate_pr:{meeting_id}",
  "message": "PR 생성 작업이 시작되었습니다."
}
```

**파일**:
- `backend/app/workers/arq_worker.py` - 자동 트리거 제거
- `backend/app/api/v1/endpoints/transcripts.py` - 수동 트리거 API 추가
