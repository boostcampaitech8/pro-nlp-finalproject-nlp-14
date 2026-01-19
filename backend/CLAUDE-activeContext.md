# Active Context - Backend

**Last Updated**: 2026-01-19
**Current Phase**: Phase 2 - PR Review System

---

## Current State

### LiveKit SFU 마이그레이션 완료 (MIT-14)
- **livekit_service.py**: 토큰 생성, Room Composite Egress 녹음 관리
- **livekit_webhooks.py**: egress_ended 이벤트로 녹음 파일 DB 저장
- **vad_event_service.py**: DataPacket VAD 이벤트 수집

### STT Pipeline (완료)
- STT Provider 추상화 (OpenAI Whisper)
- ARQ Worker 비동기 처리
- 화자별 발화 병합 (wall-clock timestamp 기반)

---

## Key Files

| 파일 | 역할 |
|------|------|
| `services/livekit_service.py` | LiveKit 토큰 생성, Egress 녹음 |
| `api/v1/endpoints/livekit_webhooks.py` | LiveKit 이벤트 웹훅 |
| `services/stt_service.py` | STT 변환 로직 |
| `services/transcript_service.py` | 회의록 병합/관리 |
| `workers/arq_worker.py` | ARQ 비동기 작업 Worker |

---

## Testing Commands

```bash
# Docker 재빌드
make docker-rebuild

# Worker 로그
docker logs -f mit-stt-worker

# STT 테스트
curl -X POST http://localhost:8000/api/v1/meetings/{id}/transcribe \
  -H "Authorization: Bearer {token}"
```
