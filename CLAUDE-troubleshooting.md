# Trouble shooting

## Troubleshooting

### 브라우저 "오류 코드: 5" (렌더러 크래시)
- **해결**: Console에서 `localStorage.clear()` 실행 후 새로고침

### shared-types 타입 인식 오류
- **해결**: `pnpm --filter @mit/shared-types build` 실행

### useWebRTC 무한 루프 (React error #185)
- **원인**: useCallback 의존성 배열에 store 전체 객체 포함
- **해결**: 전체 store 대신 개별 selector 사용: `useMeetingRoomStore((s) => s.connectionState)`

### 녹음 업로드 시 413 Request Entity Too Large
- **해결**: Presigned URL 방식으로 MinIO에 직접 업로드
  - `recordingService.uploadRecordingPresigned()` 사용

### 장시간 회의 중 401 Unauthorized
- **원인**: access token 만료 (30분)
- **해결**: useWebRTC에서 15분마다 자동 토큰 갱신 (`ensureValidToken`)

### 화면공유가 원격 참여자에게 보이지 않음
- **원인**: screen-offer 메시지가 기존 참여자에게 전달되지 않음
- **해결**: 화면공유 시작 시 모든 참여자에게 개별 피어 연결 생성 및 offer 전송
  - `startScreenShare()` 함수에서 participants 순회

### WebRTC 연결 실패 (Symmetric NAT)
- **원인**: STUN only 환경에서 제한적 NAT 타입 연결 불가
- **해결**: 현재는 같은 네트워크/호환 NAT 환경에서만 사용
- **향후**: TURN 서버 추가 필요

### IndexedDB 녹음 데이터 손실
- **원인**: 브라우저 크래시 또는 새로고침
- **해결**:
  - 10초마다 증분 저장 (RECORDING_SAVE_INTERVAL)
  - beforeunload 시 localStorage 백업
  - 재접속 시 uploadPendingRecordings() 자동 업로드

### MinIO presigned URL CORS 오류
- **원인**: MinIO CORS 설정 누락
- **해결**: MinIO 콘솔에서 CORS 설정 또는 mc 명령어로 설정
  ```bash
  mc admin policy set myminio cors-policy
  ```

### useEffect cleanup이 매 렌더링마다 실행됨
- **원인**: 훅에서 반환하는 객체가 매번 새로운 참조 생성
- **해결**: dependency array를 `[]`로 변경하고 eslint-disable 주석 추가
  ```typescript
  // unmount 시에만 실행
  useEffect(() => {
    return () => { /* cleanup */ };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  ```

### Vitest 테스트에서 signalingClient.isConnected 모킹 실패
- **원인**: `isConnected`가 getter인데 일반 속성으로 모킹
- **해결**: getter 패턴으로 mock 정의
  ```typescript
  let mockIsConnected = false;
  vi.mock('@/services/signalingService', () => ({
    signalingClient: {
      connect: vi.fn().mockImplementation(() => {
        mockIsConnected = true;
        return Promise.resolve();
      }),
      get isConnected() {
        return mockIsConnected;
      },
    },
  }));
  ```

### Docker 빌드 시 webrtcvad gcc 오류
- **증상**: `error: command 'gcc' failed: No such file or directory`
- **원인**: webrtcvad는 C 확장 빌드 필요
- **해결**: Dockerfile에 build-essential 추가
  ```dockerfile
  RUN apt-get update && apt-get install -y build-essential
  ```

### stt-worker 컨테이너 재시작 반복
- **증상**: `ModuleNotFoundError: No module named 'arq'`
- **원인**: docker-compose에서 `python -m` 대신 `uv run python -m` 필요
- **해결**: `docker-compose.yml` stt-worker command 수정
  ```yaml
  command: uv run python -m app.workers.run_worker
  ```

### webrtcvad pkg_resources 오류
- **증상**: `ModuleNotFoundError: No module named 'pkg_resources'`
- **원인**: webrtcvad가 setuptools의 pkg_resources 필요
- **해결**: pyproject.toml에 setuptools 추가
  ```toml
  "setuptools>=70.0.0",
  ```

### arq worker staticmethod 오류
- **증상**: `AttributeError: 'staticmethod' object has no attribute 'host'`
- **원인**: arq는 redis_settings를 인스턴스로 기대
- **해결**: arq_worker.py에서 staticmethod 대신 모듈 레벨 함수 사용
  ```python
  def _get_redis_settings() -> RedisSettings:
      ...

  class WorkerSettings:
      redis_settings = _get_redis_settings()  # 인스턴스
  ```

### shared-types transcript 타입 export 누락
- **증상**: `Module '"@mit/shared-types"' has no exported member 'MeetingTranscript'`
- **해결**: `packages/shared-types/src/index.ts`에 export 추가 후 빌드
  ```bash
  cd packages/shared-types && pnpm run build
  ```

### 채팅창 스크롤 안 됨
- **원인**: `min-h-screen`은 컨텐츠가 늘어나면 화면을 넘어 확장
- **해결**: flexbox 스크롤 패턴 적용
  ```tsx
  <div className="h-screen flex flex-col overflow-hidden">
    <main className="flex-1 min-h-0 flex">
      <div className="flex-1 min-h-0 overflow-y-auto">
        {/* 스크롤 영역 */}
      </div>
    </main>
  </div>
  ```

### WebRTC/TURN ICE 연결 실패 (responsesReceived: 0)
- **증상**: LiveKit 로그에서 ICE candidate pair 모두 failed, `requestsSent: 8, responsesReceived: 0`
- **원인**: 공유기에서 UDP 포트 포트포워딩 누락
- **진단 방법**:
  ```bash
  docker logs mit-livekit 2>&1 | grep -iE "ice candidate pair"
  # "state": "failed", "responsesReceived": 0 확인
  ```
- **해결**: 공유기에서 다음 포트 모두 포트포워딩:
  | 포트 | 프로토콜 | 용도 |
  |------|----------|------|
  | 5349 | TCP | TURN TLS |
  | 3478 | UDP | TURN UDP |
  | 50000-50100 | UDP | WebRTC RTC |
  | 30000-30050 | UDP | TURN relay |

### nginx stream SNI 라우팅 (443 포트 공유)
- **용도**: 443 포트 하나로 HTTPS + TURN TLS를 SNI 기반으로 분리
- **필요한 경우**: 방화벽에서 443만 열 수 있고 5349를 열 수 없을 때
- **불필요한 경우**: Docker가 5349를 직접 노출하고 공유기에서 포트포워딩 가능할 때
- **설정 예시** (필요 시):
  ```nginx
  stream {
      map $ssl_preread_server_name $backend {
          turn.mit-hub.com    livekit_turn;
          default             https_backend;
      }
      upstream livekit_turn { server 127.0.0.1:5349; }
      upstream https_backend { server 127.0.0.1:8443; }
      server {
          listen 443;
          ssl_preread on;
          proxy_pass $backend;
      }
  }
  ```
- **주의**: stream 사용 시 http 블록에서는 8443 등 다른 포트 사용 필요

### LiveKit Egress 녹음 상태 동기화 오류
- **증상**: 녹음 시작/중지 시 400 Bad Request
  - 시작 시: "Recording already active" (실제로는 녹음 없음)
  - 중지 시: "egress with status EGRESS_ABORTED cannot be stopped"
- **원인**: Backend `_active_egress` 메모리 캐시가 실제 LiveKit Egress 상태와 동기화 안됨
  - Egress가 ABORTED 되어도 메모리 캐시에 남아있음
  - Webhook에서 ABORTED 상태 처리 누락
- **Egress ABORTED 원인**: `"Start signal not received"`, `"Source closed"`
  - RoomComposite Egress Chrome이 룸 연결 전에 룸이 닫힘
  - 참여자가 너무 빨리 퇴장하거나 트랙이 없는 상태
- **해결**:
  1. `livekit_service.py`: `start_room_recording()`에서 메모리 캐시 대신 LiveKit API로 실제 상태 확인
  2. `livekit_webhooks.py`: `handle_egress_ended()`에서 모든 종료 상태(COMPLETE/FAILED/ABORTED)에서 캐시 정리
- **파일**:
  - `backend/app/services/livekit_service.py`
  - `backend/app/api/v1/endpoints/livekit_webhooks.py`
