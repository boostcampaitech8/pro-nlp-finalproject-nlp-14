# Architecture Decisions - Backend

**Last Updated**: 2026-01-11

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
**Status**: Accepted

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

## ADR-003: RecordingSession Decomposition

**Date**: 2026-01-08
**Status**: Accepted

### Context
`RecordingSession` 클래스가 7가지 책임을 가진 God Class였음:
1. WebRTC 연결 관리
2. ICE candidate 파싱
3. 미디어 녹음
4. 임시 파일 관리
5. MinIO 업로드
6. DB 저장
7. 리소스 정리

### Decision
Composition Pattern으로 분해:
- `WebRTCRecordingConnection`: 연결 관리 (1, 2, 3, 7)
- `RecordingPersistence`: 저장 관리 (4, 5, 6)
- `RecordingSession`: 코디네이터

### Consequences
**Positive**:
- 각 클래스가 단일 책임 원칙 준수
- 240줄 → 82줄로 RecordingSession 단순화
- 각 컴포넌트 독립적 테스트 가능

**Negative**:
- 파일 수 증가 (1개 → 3개)
- 간접 호출로 디버깅 시 추적 필요

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

## ADR-007: Singleton Pattern 유지 (Phase 3.3 보류)

**Date**: 2026-01-08
**Status**: Deferred

### Context
계획에는 singleton 서비스들을 DI로 전환하는 Phase 3.3이 있었음:
- `storage_service`
- `connection_manager`
- `sfu_service`

### Decision
현 단계에서는 유지. 후속 작업으로 검토.

### Rationale
- 현재 구조도 충분히 기능적
- Mock으로 테스트 가능
- DI 전환은 큰 변경이 필요
- 우선순위: 테스트 커버리지 향상이 더 시급

### Future Consideration
테스트 커버리지 80% 달성 후 재검토.

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

## ADR-011: Merge Task Timing Decision

**Date**: 2026-01-11
**Status**: Accepted

### Context
초기 구현에서 회의 종료 시 `merge_utterances_task`를 5초 후 실행하도록 큐잉. 그러나 STT가 완료되지 않은 상태에서 merge가 실행되어 `NO_TRANSCRIBED_RECORDINGS` 에러 발생.

### Decision
회의 종료 시 merge 태스크 큐잉 제거. 대신:
- `/transcribe` 호출 시 `transcribe_meeting_task` 실행
- `transcribe_meeting_task` 내에서 모든 녹음 STT 완료 후 자동으로 `merge_utterances` 호출

### Consequences
**Positive**:
- STT 완료 후에만 merge 실행 보장
- 불필요한 태스크 실패 방지
- 사용자가 STT 시작 시점 제어 가능

**Negative**:
- 자동 merge 불가 (사용자가 /transcribe 호출 필요)

### Implementation
```python
# webrtc.py end_meeting에서 제거
# await pool.enqueue_job("merge_utterances_task", ...)

# arq_worker.py transcribe_meeting_task에서 처리
if success_count > 0:
    transcript = await transcript_service.merge_utterances(meeting_uuid)
```
