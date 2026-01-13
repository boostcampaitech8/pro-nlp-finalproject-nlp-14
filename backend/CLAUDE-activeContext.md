# Active Context - Phase 2-2: Realtime Features

**Last Updated**: 2026-01-13
**Current Phase**: STT Auto-Merge 버그 수정

---

## Current Session State

### Phase 2-3: STT Auto-Merge Fix (진행 중)

#### Bug Fix (fix/merge-stt 브랜치)
- [x] 문제 분석: 개별 STT 완료 후 merge_utterances 미호출
- [x] `transcribe_recording_task`에 자동 merge 로직 추가
- [ ] 테스트 및 검증
- [ ] main 브랜치에 병합

#### 문제 원인
- 녹음 업로드 시 개별 `transcribe_recording_task` 실행
- 각 녹음 STT 완료 -> `transcribed` 상태로 변경
- **merge_utterances 호출 로직 누락** -> meeting_transcripts 테이블 비어있음

#### 해결 방법
`transcribe_recording_task` 완료 후:
1. `check_all_recordings_processed()` 호출하여 모든 녹음 처리 확인
2. 모두 완료되면 자동으로 `merge_utterances()` 실행

### Phase 2-1: STT Implementation (완료)

#### Core Features (완료)
- [x] MeetingTranscript 모델 생성
- [x] STT Provider 추상화 (OpenAI Whisper)
- [x] VAD 전처리 (발화 구간 추출)
- [x] ARQ Worker 설정
- [x] Transcription 엔드포인트 (`/transcribe`, `/transcript`, `/transcript/status`)
- [x] 화자별 발화 병합 (merge_utterances)
- [x] MinIO에 회의록 JSON 저장

### Phase 2-2: Realtime Features (완료)

#### 채팅 시스템
- [x] ChatMessage 모델 (`models/chat.py`)
- [x] ChatService (`services/chat_service.py`)
- [x] ChatMessageHandler (`handlers/websocket_message_handlers.py`)
- [x] 채팅 히스토리 API (`api/v1/endpoints/chat.py`)

#### Host 강제 음소거
- [x] ForceMuteHandler (`handlers/websocket_message_handlers.py`)
- [x] force-mute/force-muted 메시지 타입

#### Docker 빌드 수정 (2026-01-12)
- [x] Dockerfile build-essential 추가 (webrtcvad gcc 빌드)
- [x] pyproject.toml setuptools 추가 (pkg_resources)
- [x] docker-compose.yml stt-worker: `uv run python -m ...`
- [x] arq_worker.py redis_settings: staticmethod -> 인스턴스

#### Bug Fixes (2026-01-11 완료)
- [x] Recording auto-start 버그 수정 (useWebRTC refs 사용)
- [x] storage_service 메서드 추가 (`check_recording_exists`, `get_recording_size`)
- [x] transcript_service 키 이름 수정 (camelCase → snake_case)
- [x] transcripts.py ValueError 핸들링 추가
- [x] 조기 merge_utterances_task 큐잉 제거 (webrtc.py)
- [x] Dockerfile FFmpeg 추가 (pydub WebM 처리)

---

## STT Processing Flow

### 자동 처리 흐름 (개별 녹음 업로드 시)
```
1. 녹음 업로드 완료 -> POST /recordings/{id}/confirm
2. transcribe_recording_task 개별 큐잉 (ARQ)
3. ARQ Worker 처리:
   - 녹음 파일 다운로드 (MinIO)
   - VAD로 발화 구간 추출
   - OpenAI Whisper API로 STT
   - 결과 저장 (status: transcribed)
4. 모든 녹음 STT 완료 확인 -> merge_utterances 자동 실행
   - 타임스탬프 기준 정렬
   - 화자 라벨 포함 병합
   - MinIO에 JSON 저장
5. GET /meetings/{id}/transcript 로 결과 조회
```

### 수동 처리 흐름 (POST /transcribe 호출 시)
```
1. POST /meetings/{id}/transcribe 호출
2. transcribe_meeting_task 큐잉 (ARQ)
3. 모든 COMPLETED 녹음 순차 STT 처리
4. 완료 후 merge_utterances 호출
```

---

## Key Files Modified

### Backend
| 파일 | 변경 내용 |
|------|-----------|
| `api/v1/endpoints/webrtc.py` | 조기 merge_utterances_task 제거 |
| `api/v1/endpoints/transcripts.py` | ValueError 핸들링 추가 |
| `services/transcript_service.py` | 키 이름 snake_case 수정 |
| `core/storage.py` | `check_recording_exists`, `get_recording_size` 추가 |
| `Dockerfile` | FFmpeg 설치 추가 |

### Frontend
| 파일 | 변경 내용 |
|------|-----------|
| `hooks/useWebRTC.ts` | refs 사용으로 녹음 auto-start 수정 |

### Migrations
| 파일 | 역할 |
|------|------|
| `c3d4e5f6g7h8_fix_recording_status.py` | 기존 녹음 COMPLETED 상태로 업데이트 |
| `d4e5f6g7h8i9_reset_transcription_failed.py` | transcription_failed → completed 리셋 |

---

## Docker Services

```yaml
services:
  backend:
    # API 서버

  stt-worker:
    # ARQ Worker (STT 비동기 처리)
    command: uv run python -m app.workers.run_worker
    depends_on:
      - redis
      - postgres
      - minio
```

---

## Testing Commands

```bash
# Docker 재빌드 (FFmpeg 포함)
make docker-rebuild

# STT 테스트
curl -X POST http://localhost:8000/api/v1/meetings/{id}/transcribe \
  -H "Authorization: Bearer {token}"

# 상태 확인
curl http://localhost:8000/api/v1/meetings/{id}/transcript/status

# 결과 조회
curl http://localhost:8000/api/v1/meetings/{id}/transcript

# Worker 로그
docker logs -f mit-stt-worker
```

---

## Next Steps

1. **STT 정상 동작 검증**
   - Docker 재빌드 후 E2E 테스트
   - Worker 로그 확인

2. **테스트 커버리지 확장**
   - stt_service.py 테스트
   - transcript_service.py 테스트
   - arq_worker 테스트

3. **Frontend 회의록 페이지**
   - 트랜스크립트 다운로드 UI
   - 진행 상태 표시
