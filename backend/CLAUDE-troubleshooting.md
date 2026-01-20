# Troubleshooting - Backend

**Last Updated**: 2026-01-20

---

## 1. Recording Issues

### 1.1 녹음이 자동 시작되지 않음

**증상**: 회의 참여 후 녹음이 시작되지 않음

**원인**: `useWebRTC.ts`에서 `recording` 객체를 useEffect 의존성으로 사용하여 매 렌더링마다 cleanup 실행

**해결**:
```typescript
// Bad: recording 객체가 변경될 때마다 effect 재실행
useEffect(() => {
  if (connected) {
    setTimeout(() => recording.startRecording(), 500);
  }
}, [connected, recording]);  // recording이 매번 새 객체

// Good: ref 사용으로 안정적인 참조
const startRecordingRef = useRef<() => void>();
const hasStartedRecordingRef = useRef(false);

useEffect(() => {
  startRecordingRef.current = recording.startRecording;
}, [recording.startRecording]);

useEffect(() => {
  if (connected && !hasStartedRecordingRef.current) {
    hasStartedRecordingRef.current = true;
    setTimeout(() => startRecordingRef.current?.(), 500);
  }
}, [connected]);  // 최소 의존성
```

**파일**: `frontend/src/hooks/useWebRTC.ts`

---

### 1.2 /confirm 엔드포인트 500 에러

**증상**: 녹음 업로드 후 `/confirm` 호출 시 500 에러

**원인**: `storage_service`에 `check_recording_exists()`, `get_recording_size()` 메서드 누락

**해결**: `core/storage.py`에 메서드 추가
```python
def check_recording_exists(self, file_path: str) -> bool:
    return self.check_file_exists(self.BUCKET_RECORDINGS, file_path)

def get_recording_size(self, file_path: str) -> int:
    info = self.get_file_info(self.BUCKET_RECORDINGS, file_path)
    return info["size"] if info else 0
```

**파일**: `backend/app/core/storage.py`

---

### 1.3 LiveKit Egress 녹음 상태 동기화 오류

**증상**: 녹음 시작/중지 시 400 Bad Request
- 시작: "Recording already active" (실제로는 녹음 없음)
- 중지: "egress with status EGRESS_ABORTED cannot be stopped"

**원인**: `_active_egress` 메모리 캐시가 실제 LiveKit Egress 상태와 동기화 안됨
- Egress ABORTED 시 webhook에서 캐시 정리 누락
- `start_room_recording()`이 메모리 캐시만 확인

**Egress ABORTED 원인** (`"Start signal not received"`, `"Source closed"`):
- RoomComposite Egress Chrome이 룸 연결 전에 룸이 닫힘
- 참여자가 너무 빨리 퇴장하거나 트랙이 없는 상태

**해결**:
```python
# livekit_service.py - start_room_recording()
# 메모리 캐시 대신 LiveKit API로 실제 상태 확인
async with api.LiveKitAPI(...) as lk_api:
    response = await lk_api.egress.list_egress(
        api.ListEgressRequest(room_name=room_name, active=True)
    )
    if response.items:
        return response.items[0].egress_id  # 이미 활성
    # 캐시에 있지만 실제로 없으면 정리
    if meeting_key in self._active_egress:
        del self._active_egress[meeting_key]

# livekit_webhooks.py - handle_egress_ended()
# 모든 종료 상태에서 캐시 정리
livekit_service.clear_active_egress(meeting_id)
```

**파일**:
- `backend/app/services/livekit_service.py`
- `backend/app/api/v1/endpoints/livekit_webhooks.py`

---

## 2. STT Issues

### 2.1 /transcript/status 500 에러

**증상**: STT 상태 조회 시 500 Internal Server Error

**원인 1**: `transcript_service.py`에서 키 이름이 camelCase로 반환되어 endpoint에서 snake_case로 접근 시 KeyError

**해결 1**:
```python
# Bad
return {
    "transcriptId": str(transcript.id),
    "totalRecordings": len(completed_recordings),
}

# Good
return {
    "transcript_id": str(transcript.id),
    "total_recordings": len(completed_recordings),
}
```

**원인 2**: `transcripts.py` endpoint에서 ValueError 핸들링 누락

**해결 2**:
```python
except ValueError as e:
    error_code = str(e)
    if error_code == "TRANSCRIPT_NOT_FOUND":
        raise HTTPException(status_code=404, detail={...})
    if error_code == "MEETING_NOT_FOUND":
        raise HTTPException(status_code=404, detail={...})
```

**파일**:
- `backend/app/services/transcript_service.py`
- `backend/app/api/v1/endpoints/transcripts.py`

---

### 2.2 NO_TRANSCRIBED_RECORDINGS 에러

**증상**: Worker 로그에 `ValueError: NO_TRANSCRIBED_RECORDINGS`

**원인**: 회의 종료 시 `merge_utterances_task`가 5초 후 실행되도록 큐잉되는데, STT가 완료되지 않은 상태에서 merge 시도

**해결**: `webrtc.py` `end_meeting`에서 `merge_utterances_task` 큐잉 제거
```python
# 제거됨
# await pool.enqueue_job("merge_utterances_task", str(meeting_id), _defer_by=5)
```

**파일**: `backend/app/api/v1/endpoints/webrtc.py`

---

### 2.3 meeting_transcripts 테이블이 비어있음 (개별 STT 완료 후 merge 안됨)

**증상**:
- 모든 녹음이 `transcribed` 상태
- `meeting_transcripts` 테이블에 레코드 없음
- POST /transcribe 호출 시 400 `NO_COMPLETED_RECORDINGS` 에러

**원인**:
- 녹음 업로드 시 개별 `transcribe_recording_task`가 실행됨
- 각 녹음 STT 완료 후 `merge_utterances` 호출 로직 누락
- `transcribe_meeting_task`는 `COMPLETED` 상태 녹음만 처리 (이미 `TRANSCRIBED`면 무시)

**해결**: `transcribe_recording_task`에 자동 merge 로직 추가
```python
# arq_worker.py
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
**브랜치**: `fix/merge-stt`

---

### 2.4 KeyError: 'speaker_id' in transcript response

**증상**: GET /transcript 호출 시 500 에러, `KeyError: 'speaker_id'`

**원인**: `Utterance.to_dict()`는 camelCase(`speakerId`)로 저장하는데, endpoint에서 snake_case(`speaker_id`)로 읽으려 함

**해결**: endpoint에서 camelCase 키 사용
```python
# Bad
speaker_id=u["speaker_id"],
speaker_name=u["speaker_name"],

# Good
speaker_id=u["speakerId"],
speaker_name=u["speakerName"],
```

**파일**: `backend/app/api/v1/endpoints/transcripts.py`

---

### 2.5 Transcript download URL not working

**증상**: Download JSON 버튼 클릭 시 다운로드 안됨

**원인**: `get_presigned_url()`이 내부 MinIO URL(`http://minio:9000/...`) 반환. 브라우저에서 접근 불가.

**해결**: 외부 URL로 변환 추가
```python
def get_presigned_url(...) -> str:
    url = client.presigned_get_object(...)
    # 내부 URL을 외부 프록시 URL로 변환
    internal_url = f"http://{settings.minio_endpoint}"
    external_url = settings.storage_external_url
    return url.replace(internal_url, external_url)
```

**파일**: `backend/app/core/storage.py`

---

### 2.6 All recordings failed to transcribe

**증상**: STT 시작 후 모든 녹음 변환 실패

**원인**: Dockerfile에 FFmpeg 미설치. pydub가 WebM 오디오를 디코딩하려면 FFmpeg 필요.

**해결**: Dockerfile에 FFmpeg 추가
```dockerfile
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    ffmpeg \  # 추가
    && rm -rf /var/lib/apt/lists/*
```

**파일**: `backend/Dockerfile`

**재배포**:
```bash
make docker-rebuild
# 또는
docker-compose up -d --build backend stt-worker
```

---

## 3. Migration Issues

### 3.1 기존 녹음이 PENDING 상태로 남아있음

**증상**: MinIO에 파일이 있지만 DB 상태가 PENDING

**원인**: 녹음 업로드 후 `/confirm` 실패로 상태 미갱신

**해결**: 마이그레이션으로 일괄 업데이트
```python
# c3d4e5f6g7h8_fix_recording_status.py
op.execute("""
    UPDATE meeting_recordings
    SET status = 'completed'
    WHERE status IN ('pending', 'recording')
    AND file_path IS NOT NULL
    AND file_path != ''
""")
```

---

### 3.2 transcription_failed 상태 리셋

**증상**: 이전 STT 실패로 `transcription_failed` 상태인 녹음 재처리 필요

**해결**: 마이그레이션으로 리셋
```python
# d4e5f6g7h8i9_reset_transcription_failed.py
op.execute("""
    UPDATE meeting_recordings
    SET status = 'completed'
    WHERE status = 'transcription_failed'
""")
```

---

## 4. Docker Issues

### 4.1 Worker 컨테이너 로그 확인

```bash
# Worker 로그 실시간 확인
docker logs -f mit-stt-worker

# 최근 100줄만
docker logs --tail 100 mit-stt-worker

# 특정 시간 이후
docker logs --since 1h mit-stt-worker
```

### 4.2 컨테이너 내부 디버깅

```bash
# 컨테이너 진입
docker exec -it mit-stt-worker bash

# Python REPL로 테스트
docker exec -it mit-stt-worker python
>>> from app.core.storage import storage_service
>>> storage_service.check_recording_exists("some/path.webm")
```

### 4.3 Redis 작업 큐 확인

```bash
# Redis CLI 접속
docker exec -it mit-redis redis-cli

# ARQ 큐 확인
KEYS arq:*
LRANGE arq:queue 0 -1
```
