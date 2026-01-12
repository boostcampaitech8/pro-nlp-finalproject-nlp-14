# Code Patterns - Backend

**Last Updated**: 2026-01-11

---

## 1. API Endpoint Patterns

### 1.1 Shared Dependencies 사용

**Pattern**: FastAPI Depends()를 활용한 공통 로직 재사용

```python
from app.api.dependencies import get_current_user, require_meeting_participant

@router.get("/{meeting_id}/recordings")
async def get_meeting_recordings(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    current_user: Annotated[User, Depends(get_current_user)],
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
):
    # 검증 로직 불필요 - dependency에서 처리
    recordings = await recording_service.get_meeting_recordings(meeting.id)
    return [...]
```

**Benefits**:
- 180+ lines 중복 코드 제거
- 권한 체크 로직 중앙화
- 테스트 시 dependency override 용이

### 1.2 Service Layer 패턴

**Pattern**: 비즈니스 로직을 서비스 클래스로 분리

```python
# Endpoint - HTTP 처리만
@router.post("/{meeting_id}/recordings/upload-url")
async def get_recording_upload_url(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    recording_service: Annotated[RecordingService, Depends(get_recording_service)],
    request: RecordingUploadUrlRequest,
):
    try:
        result = await recording_service.create_recording_upload(...)
        return RecordingUploadUrlResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Service - 비즈니스 로직
class RecordingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_recording_upload(self, meeting_id, user_id, ...):
        self.validate_file_size(file_size_bytes)
        # 비즈니스 로직...
```

---

## 2. WebSocket Message Handling

### 2.1 Strategy Pattern

**Pattern**: 메시지 타입별 핸들러 클래스 분리

```python
# Protocol 정의
class MessageHandler(Protocol):
    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        ...

# 통합 핸들러 (재사용)
class OfferAnswerHandler:
    def __init__(self, message_type: str):
        self.message_type = message_type

    async def handle(self, meeting_id, user_id, data):
        # offer/answer 공통 로직

# 핸들러 레지스트리
HANDLERS: dict[str, MessageHandler] = {
    SignalingMessageType.JOIN: JoinHandler(),
    SignalingMessageType.OFFER: OfferAnswerHandler("offer"),
    SignalingMessageType.ANSWER: OfferAnswerHandler("answer"),
    # ...
}

# 디스패치
async def dispatch_message(msg_type, meeting_id, user_id, data) -> bool:
    if msg_type == SignalingMessageType.LEAVE:
        return False
    handler = HANDLERS.get(msg_type)
    if handler:
        await handler.handle(meeting_id, user_id, data)
    return True
```

**Benefits**:
- 새 메시지 타입 추가 용이 (클래스 추가 + 레지스트리 등록)
- 각 핸들러 독립적 테스트 가능
- if-elif 체인 제거

---

## 3. Class Composition

### 3.1 God Class 분해

**Pattern**: 여러 책임을 가진 클래스를 전문 클래스로 분해 후 조합

```python
# Coordinator (조율자)
class RecordingSession:
    def __init__(self, meeting_id: UUID, user_id: UUID):
        # Composition: 책임을 전문 클래스에 위임
        self.connection = WebRTCRecordingConnection(meeting_id, user_id)
        self.persistence = RecordingPersistence()

    async def setup(self):
        return await self.connection.setup()  # 위임

    async def stop_and_save(self, db):
        ended_at = await self.connection.stop_recorder()
        return await self.persistence.save_recording(...)  # 위임

# Specialist 1: 연결 관리
class WebRTCRecordingConnection:
    # RTCPeerConnection, MediaRecorder, ICE handling

# Specialist 2: 저장 관리
class RecordingPersistence:
    # MinIO upload, DB save, temp file cleanup
```

**Benefits**:
- 각 클래스가 단일 책임 원칙 준수
- 독립적 테스트 가능
- 코드 재사용성 향상

---

## 4. Error Handling

### 4.1 Service Layer 에러 → HTTP 변환

**Pattern**: Service에서 ValueError 발생, Endpoint에서 HTTPException 변환

```python
# Service
class RecordingService:
    def validate_file_size(self, file_size: int):
        if file_size > MAX_RECORDING_FILE_SIZE:
            raise ValueError("FILE_TOO_LARGE")

# Endpoint
try:
    result = await recording_service.create_recording_upload(...)
except ValueError as e:
    error_code = str(e)
    if error_code == "FILE_TOO_LARGE":
        raise HTTPException(
            status_code=400,
            detail={"error": "BAD_REQUEST", "message": "파일 크기가 너무 큽니다."}
        )
```

---

## 5. Constants Management

### 5.1 중앙화된 상수

**Pattern**: 매직 넘버를 constants.py로 중앙화

```python
# app/core/constants.py
MAX_RECORDING_FILE_SIZE = 500 * 1024 * 1024  # 500MB
PRESIGNED_URL_EXPIRATION = 3600  # 1 hour
SUPPORTED_RECORDING_FORMATS = ["webm", "mp4", "mkv"]

# 사용
from app.core.constants import MAX_RECORDING_FILE_SIZE
```

---

## 6. Testing Patterns

### 6.1 Service Mock

**Pattern**: Service layer를 mock하여 endpoint 테스트

```python
@pytest.fixture
def mock_recording_service():
    with patch("app.services.recording_service.storage_service") as mock:
        mock.get_recording_upload_url.return_value = ("url", "path")
        mock.check_recording_exists.return_value = True
        yield mock

async def test_upload_recording(mock_recording_service, client):
    response = await client.post("/meetings/{id}/recordings/upload-url", ...)
    assert response.status_code == 200
```

### 6.2 Dependency Override

**Pattern**: FastAPI dependency를 테스트용으로 override

```python
def override_get_current_user():
    return mock_user

app.dependency_overrides[get_current_user] = override_get_current_user
```

---

## 7. ARQ Worker Patterns

### 7.1 Async Task Definition

**Pattern**: ARQ 비동기 태스크 정의

```python
# workers/arq_worker.py
async def transcribe_meeting_task(ctx: dict, meeting_id: str, language: str = "ko") -> dict:
    """비동기 태스크 함수

    Args:
        ctx: ARQ 컨텍스트 (자동 주입)
        meeting_id: 처리할 회의 ID (문자열)
        language: 옵션 파라미터

    Returns:
        dict: 작업 결과 (status, error 등)
    """
    meeting_uuid = UUID(meeting_id)

    async with async_session_maker() as db:
        service = SomeService(db)
        try:
            result = await service.process(meeting_uuid)
            return {"status": "success", "data": result}
        except Exception as e:
            logger.exception(f"Task failed: {meeting_id}")
            return {"status": "failed", "error": str(e)}

# Worker 설정
class WorkerSettings:
    functions = [transcribe_meeting_task]
    redis_settings = _get_redis_settings()
    max_tries = 3
    job_timeout = 3600
```

### 7.2 Task Queueing

**Pattern**: 엔드포인트에서 비동기 태스크 큐잉

```python
from arq import ArqRedis, create_pool

async def get_arq_pool() -> ArqRedis:
    settings = get_settings()
    return await create_pool(RedisSettings(...))

@router.post("/{meeting_id}/transcribe")
async def start_transcription(meeting_id: UUID):
    pool = await get_arq_pool()
    await pool.enqueue_job(
        "transcribe_meeting_task",
        str(meeting_id),  # UUID는 문자열로 전달
        "ko",             # 추가 파라미터
    )
    await pool.close()
    return {"status": "accepted"}
```

---

## 8. Provider Pattern

### 8.1 Abstract Provider

**Pattern**: 외부 서비스 추상화

```python
# services/stt/base.py
from abc import ABC, abstractmethod

class STTProvider(ABC):
    """STT Provider 추상 클래스"""

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "ko",
        **kwargs
    ) -> TranscriptionResult:
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

# services/stt/openai_provider.py
class OpenAIWhisperProvider(STTProvider):
    async def transcribe(self, audio_data, language="ko", **kwargs):
        # OpenAI API 호출
        ...

    @property
    def provider_name(self) -> str:
        return "openai_whisper"

# services/stt/factory.py
class STTProviderFactory:
    @staticmethod
    def create(provider_type: str = "openai") -> STTProvider:
        if provider_type == "openai":
            return OpenAIWhisperProvider()
        raise ValueError(f"Unknown provider: {provider_type}")
```

**Benefits**:
- 외부 서비스 교체 용이 (OpenAI → Local Whisper)
- 테스트 시 Mock Provider 주입 가능
- 설정으로 Provider 선택 가능

---

## 9. React Refs for Stable References

### 9.1 useRef로 의존성 순환 방지

**Pattern**: useEffect 내에서 안정적인 함수 참조

```typescript
// hooks/useWebRTC.ts
const startRecordingRef = useRef<() => void>();
const hasStartedRecordingRef = useRef(false);

// Ref에 함수 할당
useEffect(() => {
  startRecordingRef.current = recording.startRecording;
}, [recording.startRecording]);

// 안정적인 참조로 useEffect 실행
useEffect(() => {
  if (connectionState === 'connected' && !hasStartedRecordingRef.current) {
    hasStartedRecordingRef.current = true;
    const timer = setTimeout(() => {
      startRecordingRef.current?.();
    }, 500);
    return () => clearTimeout(timer);
  }
}, [connectionState]);  // 최소 의존성
```

**Why**:
- `recording` 객체를 의존성으로 넣으면 매 렌더링마다 cleanup 실행
- useRef는 리렌더링 없이 값 유지
- 의존성 배열 최소화로 불필요한 effect 재실행 방지
