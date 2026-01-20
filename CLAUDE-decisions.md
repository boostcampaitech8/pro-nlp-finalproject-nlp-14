# Architecture Decisions

## WebRTC / LiveKit

### D26: LiveKit SFU 마이그레이션
- **결정**: Mesh P2P에서 LiveKit SFU로 아키텍처 전환
- **근거**:
  - 서버 측 녹음 필요 (실시간 STT 준비)
  - 클라이언트 녹음 안정성 문제 (브라우저 크래시, 네트워크 끊김)
  - 확장성 (참여자 수 증가 시 Mesh O(n^2) 연결 한계)
  - 중앙 서버에서 미디어 제어 용이 (강제 음소거 등)
- **구현**:
  - Docker: livekit, livekit-egress 서비스 추가
  - Backend: LiveKitService (토큰 생성), livekit_webhooks (이벤트 수신)
  - Frontend: useLiveKit 훅 (useWebRTC 인터페이스 유지)
- **DataPacket 활용**:
  - VAD 이벤트: 발화 시작/끝 서버 전송
  - 채팅: RELIABLE 모드로 실시간 메시지
  - 강제 음소거: Host -> Target 제어 메시지
- **녹음**:
  - LiveKit Egress로 서버 측 녹음
  - MinIO에 직접 저장
  - egress_ended 웹훅으로 STT 큐잉
- **호환성**:
  - 기존 useWebRTC 인터페이스 유지 (MeetingRoom 변경 최소화)
  - localStorage 캐싱 로직 그대로 유지

### D27: LiveKit Egress 설정 방식
- **결정**: `EGRESS_CONFIG_BODY` 환경변수로 인라인 YAML 설정 전달
- **근거**:
  - `EGRESS_CONFIG_FILE` + 파일 마운트 방식에서 설정 파싱 문제 발생
  - docker-compose의 `${VAR}` 치환이 인라인 설정에서 정상 동작
  - `LIVEKIT_CONFIG`와 동일한 패턴으로 일관성 유지
- **지원되는 환경변수** (공식 문서):
  - `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_WS_URL` - 지원됨
  - `REDIS_ADDRESS` - **지원 안 됨** (반드시 config에 설정)
- **참고**: https://docs.livekit.io/home/self-hosting/egress/

### D28: nginx LiveKit WebSocket 프록시
- **결정**: `/livekit/` 경로를 LiveKit 서버로 WebSocket 프록시
- **근거**:
  - 클라이언트가 `wss://domain.com/livekit/`로 연결
  - nginx에서 `livekit:7880`으로 프록시
  - 장시간 연결 유지를 위해 7일 타임아웃 설정
- **구현**: `frontend/nginx.conf`
  ```nginx
  location /livekit/ {
      proxy_pass http://livekit:7880/;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
      proxy_connect_timeout 7d;
      proxy_send_timeout 7d;
      proxy_read_timeout 7d;
  }
  ```

### D30: LiveKit TURN TLS 활성화
- **결정**: LiveKit 내장 TURN 서버를 TLS 모드로 활성화
- **근거**:
  - NAT/방화벽 환경에서 WebRTC 연결 성공률 향상 (85% -> 99%+)
  - 기업 네트워크, 호텔/공항 WiFi 등 제한적 환경 대응
  - TLS 포트(5349)는 HTTPS 트래픽으로 보여 방화벽 통과 용이
- **구현**:
  - 도메인: `turn.mit-hub.com` (Let's Encrypt 인증서)
  - 인증서 마운트: `/etc/letsencrypt:/etc/letsencrypt:ro` (심볼릭 링크 유지)
- **필수 포트포워딩** (공유기/방화벽):
  | 포트 | 프로토콜 | 용도 |
  |------|----------|------|
  | 5349 | TCP | TURN TLS |
  | 3478 | UDP | TURN UDP |
  | 50000-50100 | UDP | WebRTC RTC |
  | 30000-30050 | UDP | TURN relay |
- **nginx stream (선택적)**:
  - 5349 직접 노출 가능하면 불필요
  - 443만 열 수 있는 환경에서만 SNI 기반 라우팅 설정
- **Trade-off**:
  - 장점: 연결 성공률 대폭 향상
  - 단점: 인증서 관리 필요, TURN 경유 시 대역폭 증가
- **설정 위치**: `docker/docker-compose.yml` livekit 서비스
- **참고**: https://docs.livekit.io/realtime/self-hosting/deployment/#turn-configuration

### D31: LiveKit 웹훅 서명 검증
- **결정**: TokenVerifier + WebhookReceiver 패턴으로 서명 검증
- **근거**:
  - 보안: 웹훅 요청이 실제 LiveKit 서버에서 왔는지 검증 필수
  - livekit-api SDK 업데이트로 API 시그니처 변경됨
- **구현**: `backend/app/api/v1/endpoints/livekit_webhooks.py`
  ```python
  token_verifier = api.TokenVerifier(api_key, api_secret)
  webhook_receiver = api.WebhookReceiver(token_verifier)
  event = webhook_receiver.receive(body.decode(), authorization)
  # MessageToDict로 camelCase 변환 (preserving_proto_field_name=False)
  return MessageToDict(event, preserving_proto_field_name=False)
  ```
- **주의**:
  - `preserving_proto_field_name=False` 필수 (camelCase 필드명)
  - SDK 버전 변경 시 API 시그니처 확인 필요

### D32: Redis 기반 Egress 상태 관리
- **결정**: 메모리 캐시 대신 Redis로 활성 Egress 상태 저장
- **근거**:
  - 서버 재시작 시에도 상태 유지
  - 다중 인스턴스 환경에서 상태 공유 가능
  - 24시간 TTL로 자동 만료 (orphan 방지)
- **구현**: `backend/app/services/livekit_service.py`
  ```python
  EGRESS_KEY_PREFIX = "livekit:egress:"
  EGRESS_TTL_SECONDS = 86400  # 24시간

  async def _set_active_egress(self, meeting_id: UUID, egress_id: str):
      redis = await get_redis()
      await redis.set(f"{EGRESS_KEY_PREFIX}{meeting_id}", egress_id, ex=EGRESS_TTL_SECONDS)
  ```
- **Redis 클라이언트**: `backend/app/core/redis.py` (싱글톤 패턴)

### D29: LiveKit rtcConfig 배치
- **결정**: `rtcConfig`는 Room constructor가 아닌 `room.connect()` 메서드에 전달
- **근거**:
  - LiveKit SDK 2.17.0 타입 정의 분석:
    - `RoomOptions` (Room constructor) - `adaptiveStream`, `dynacast` 등만 포함
    - `RoomConnectOptions` (room.connect()) - `rtcConfig` 포함
  - TypeScript TS2353 에러: `rtcConfig does not exist in type Partial<InternalRoomOptions>`
- **구현**:
  ```typescript
  // Room 생성 - rtcConfig 없음
  const room = new Room({
    adaptiveStream: true,
    dynacast: true,
  });

  // 연결 시 rtcConfig 전달
  await room.connect(wsUrl, token, {
    rtcConfig: {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
      ],
      iceTransportPolicy: 'all',
    },
  });
  ```
- **참고**: LiveKit SDK 버전 업그레이드 시 타입 정의 변경 확인 필요

## Storage & Authentication

> **상세 Backend ADR**: `backend/CLAUDE-decisions.md` 참조

### D4: Presigned URL 업로드
- MinIO 직접 업로드 (nginx 크기 제한 우회, 서버 메모리 부하 감소)

### D5: IndexedDB 증분 저장
- 10초마다 IndexedDB 저장 (브라우저 크래시 대비)

### D6: JWT + 자동 갱신
- 30분 access + 7일 refresh, 회의 중 15분마다 자동 갱신

## State Management

### D7: Zustand 개별 Selector
- 스토어 전체 대신 개별 selector 사용 (무한 루프 방지)

## API Design

### D8: API Contract First
- OpenAPI 명세가 SSOT, FE/BE 타입 일관성 보장

### D9: UUID 사용
- 모든 엔티티에 UUID (분산 시스템 확장성, ID 추측 공격 방지)

### D12: 페이지네이션 표준화
- 모든 목록 API는 `items` + `meta` 형식

### D13: OpenAPI allOf 합성
- 확장 스키마에 allOf 패턴 사용 (DRY 원칙)

### D14: 스키마 파일 통합
- 작은 스키마를 도메인 파일에 통합 (team-member -> team)

## Frontend Architecture

### D11: 페이지 컴포넌트 분리
- 대형 페이지를 기능별 섹션 컴포넌트로 분리 (MeetingDetailPage -> InfoCard, ParticipantSection, RecordingList)

### D15: LocalStorage 사용자 설정 캐싱
- 오디오 설정을 localStorage에 캐싱, 스토어 reset() 시에도 유지
- 저장: `mit-audio-settings`, `mit-remote-volumes`

## STT & Transcript

### D16: Transcript 실제 시각 저장
- wall-clock timestamp 저장 (`recording.started_at + startMs`)
- 여러 참여자 녹음 병합 시 실제 대화 순서 보장
- UI에서 실제 발화 시각 표시 (HH:MM:SS)

## UI Architecture

### D17: Spotlight-style 메인 서비스 페이지
- 3-column 레이아웃: 좌측 280px + 중앙 flex + 우측 400px
- 자연어 명령어 + 컨텍스트 미리보기

### D18: Glassmorphism 디자인 시스템
- `backdrop-filter: blur()`, `rgba()` 배경색, 커스텀 Tailwind 색상
- 주의: 중첩 blur 최소화 (성능)

### D19: Modal Store 분리 패턴
- 모달 상태를 별도 Zustand 스토어로 관리 (여러 위치에서 열기 가능)

### D20: Command System 아키텍처
- 패턴 매칭 기반 명령어 시스템 (한글/영어, 자동완성, 히스토리)
- 응답 타입: direct, navigation, modal, form

## Code Quality

### D21-D25: Frontend 코드 품질 결정
- **D21**: Constants 중앙 관리 (`constants/index.ts`)
- **D22**: Type Guard 우선 사용 (`as` 대신)
- **D23**: Form State 통합 (단일 formData 객체)
- **D24**: useRef for Non-UI State (re-render 방지)
- **D25**: Suggestions SSOT (agentService에서만 관리)

### D34: agentService 리팩토링
- **결정**: agentService를 3개 파일로 분리 (데이터, 매칭, 서비스)
- **근거**:
  - God Object 패턴 해소 (384 lines -> ~146 lines)
  - Cyclomatic complexity 감소 (matchCommand 12 -> ~3)
  - 단일 책임 원칙 적용
- **구현**:
  - `mockResponses.ts`: Mock 응답 데이터 정의
  - `commandMatcher.ts`: Strategy Pattern으로 명령어 매칭
  - `agentService.ts`: 비즈니스 로직 (processCommand, submitForm)
- **Trade-off**:
  - 장점: 유지보수성 향상, 테스트 용이, Mock -> 실제 API 전환 용이
  - 단점: 파일 수 증가 (1 -> 3)

### D35: Hook 중복 코드 유틸리티 추출
- **결정**: useCommand와 useConversationCommand의 중복 코드를 공유 유틸리티로 추출
- **근거**:
  - 동일 로직 ~60 lines 중복 (preview 업데이트, history 생성)
  - DRY 원칙 위반
- **구현**:
  - `utils/previewUtils.ts`: `updatePreviewStore`, `isValidPreviewType`
  - `utils/historyUtils.ts`: `createSuccessHistoryItem`, `createErrorHistoryItem`
- **Trade-off**:
  - 장점: 중복 제거, 일관된 동작 보장, 변경 시 단일 지점 수정
  - 단점: 간접 참조 증가

### D33: Conversation Mode Architecture
- **결정**: Spotlight 입력창을 채팅 인터페이스로 변환하는 대화 모드 구현
- **근거**:
  - 감성적인 대화형 UX 제공 (명령어 -> 채팅 버블)
  - 폼 입력을 대화 흐름에 자연스럽게 통합
  - 다양한 레이아웃 모드로 사용자 선호도 지원
- **구현**:
  - 스토어: `conversationStore.ts` (Zustand + persist)
  - 메시지 타입: `user`, `agent`, `system`
  - 레이아웃: `fullscreen` (기본값), `center-only`, `center-right-merged`
  - 마크다운 렌더링: AgentMessageBubble에서 previewData.content를 MarkdownRenderer로 표시
- **컴포넌트 구조**:
  ```
  frontend/src/app/components/conversation/
  ├── ConversationContainer.tsx   # 메인 컨테이너
  ├── ChatMessageList.tsx         # 메시지 목록 (자동 스크롤)
  ├── ChatMessage.tsx             # 메시지 라우터
  ├── UserMessageBubble.tsx       # 사용자 버블 (우측)
  ├── AgentMessageBubble.tsx      # 에이전트 버블 (좌측)
  ├── SystemMessageBubble.tsx     # 시스템 버블 (중앙)
  ├── EmbeddedForm.tsx            # 채팅 내 폼
  ├── ChatSpotlightInput.tsx      # 하단 고정 입력창
  └── TypingIndicator.tsx         # 로딩 표시
  ```
- **Closure 문제 해결**:
  - 문제: async 콜백에서 훅 값이 생성 시점에 캡처됨
  - 해결: `useConversationStore.getState()`로 최신 상태 조회
- **Trade-off**:
  - 장점: 직관적 대화형 UX, 폼 통합
  - 단점: 추가 상태 관리 복잡도
