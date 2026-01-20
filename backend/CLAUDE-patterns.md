# Code Patterns - Backend

**Last Updated**: 2026-01-20

> **공통 패턴은 `CLAUDE-patterns.md` (루트) 참조**
> - Redis Client Singleton Pattern
> - LiveKit Webhook Signature Verification Pattern
> - Egress State Management Pattern (Redis)

---

## 1. API Endpoint Patterns

### 1.1 Shared Dependencies
- FastAPI `Depends()`로 인증/권한 체크 중앙화
- `app/api/dependencies.py`에 공통 dependency 정의
- 180+ lines 중복 제거, 테스트 시 override 용이

### 1.2 Service Layer
- Endpoint: HTTP 처리만 (validation, response 형식화)
- Service: 비즈니스 로직 (DB 조회, 상태 변경, 외부 서비스 호출)
- ValueError → HTTPException 변환 패턴

---

## 2. Strategy Pattern (Event Handlers)
- 이벤트 타입별 Handler 클래스 분리 (`MessageHandler` Protocol)
- 핸들러 레지스트리 방식으로 디스패치
- if-elif 체인 제거, 새 이벤트 타입 추가 용이

---

## 3. Class Composition
- God Class → Coordinator + Specialists로 분해
- 단일 책임 원칙 준수, 독립 테스트 가능

---

## 4. Error Handling
- Service: `ValueError("ERROR_CODE")` 발생
- Endpoint: 에러 코드별 `HTTPException` 변환

---

## 5. Constants
- `app/core/constants.py`에 매직 넘버 중앙화
- `MAX_RECORDING_FILE_SIZE`, `PRESIGNED_URL_EXPIRATION` 등

---

## 6. Testing
- Service layer mock으로 endpoint 테스트
- `app.dependency_overrides`로 dependency 교체

---

## 7. ARQ Worker
- 태스크 함수: `ctx` (자동 주입) + 파라미터 (UUID는 문자열로 전달)
- `WorkerSettings`: functions, redis_settings, max_tries, job_timeout
- 엔드포인트에서 `pool.enqueue_job("task_name", args...)` 큐잉

---

## 8. Provider Pattern
- `STTProvider` ABC로 외부 서비스 추상화
- `OpenAIWhisperProvider` 등 구현체
- `STTProviderFactory`로 Provider 생성
- 외부 서비스 교체/테스트 용이

