# Code Patterns

## Frontend Patterns

### State Management (Zustand)
- **스토어 분리**: 기능별 스토어 분리 (authStore, teamStore, meetingRoomStore)
- **Selector 패턴**: 무한 루프 방지를 위해 개별 selector 사용
  ```typescript
  // Good
  const connectionState = useMeetingRoomStore((s) => s.connectionState);

  // Bad - 무한 루프 발생 가능
  const store = useMeetingRoomStore();
  ```

### LiveKit Hook (useLiveKit) - 현재 사용
- **위치**: `frontend/src/hooks/useLiveKit.ts`
- **역할**: LiveKit SFU 연결, 미디어 관리, 채팅, VAD 이벤트 (핵심 훅)
- **주요 상태**: `connectionState`, `participants`, `localStream`, `remoteStreams`, `isAudioMuted`, `isRecording`, `chatMessages`
- **오디오 설정**: `micGain`, `audioInputDeviceId`, `audioOutputDeviceId`, `remoteVolumes` (localStorage 캐싱)
- **주요 액션**: `joinRoom`, `leaveRoom`, `toggleMute`, `forceMute`, `sendChatMessage`, `startScreenShare`
- **핵심 패턴**:
  ```typescript
  // Room 연결 (rtcConfig는 connect()에 전달)
  const room = new Room({ adaptiveStream: true, dynacast: true });
  await room.connect(wsUrl, token, { rtcConfig: { iceServers: [...] } });

  // DataPacket 전송 (채팅, VAD, 강제 음소거)
  room.localParticipant.publishData(
    new TextEncoder().encode(JSON.stringify({ type: 'chat', content })),
    { reliable: true }
  );

  // Web Audio GainNode로 볼륨 조절
  gainNode.gain.value = micGain;
  source.connect(gainNode).connect(destination);
  ```


### Audio Processing
- **GainNode**: 마이크 볼륨 조절 (0.0 ~ 2.0)
- **processedAudioRef**: Web Audio API로 처리된 스트림 관리
- **디바이스 선택**: useAudioDevices 훅으로 입/출력 장치 관리

### Chat System (DataPacket 기반)
- **위치**: `frontend/src/components/meeting/ChatPanel.tsx`
- **기능**:
  - LiveKit DataPacket (RELIABLE 모드)으로 실시간 메시지 전송/수신
  - DB 저장으로 히스토리 유지
  - 회의 입장 시 GET /meetings/{id}/chat으로 히스토리 로드
  - Markdown 렌더링 지원
  - 연속 메시지 그룹화 (같은 사람, 1분 이내)
  - Shift+Enter 줄바꿈, Enter 전송
- **DataPacket 구조**:
  ```typescript
  interface ChatDataPacket {
    type: 'chat';
    content: string;
    userId: string;
    userName: string;
    timestamp: string;
  }
  ```
- **Props**:
  - `hideHeader`: 헤더 숨김 (접이식 UI용)
  - `currentUserId`: 본인 메시지 구분

### Force Mute (Host 강제 음소거 - DataPacket 기반)
- **메시지 플로우**:
  ```
  Host -> DataPacket {type: 'force-mute', targetUserId, muted} -> LiveKit Server
  LiveKit Server -> DataPacket forward -> Target Participant
  Target -> setMicrophoneEnabled(!muted)
  ```
- **DataPacket 구조**:
  ```typescript
  interface ForceMutePacket {
    type: 'force-mute';
    targetUserId: string;
    muted: boolean;
    byUserId: string;
  }
  ```
- **권한 검증**: useLiveKit 훅에서 participant role 확인

### Collapsible Sidebar Pattern
- **상태**: `showParticipants`, `showChat` (useState)
- **구조**:
  ```tsx
  <aside className="flex flex-col">
    <button onClick={() => setShowSection(!showSection)}>
      <span>섹션 제목</span>
      <ChevronIcon className={showSection ? 'rotate-180' : ''} />
    </button>
    {showSection && <SectionContent />}
  </aside>
  ```

### Flexbox Scroll Pattern
- **문제**: `min-h-screen`은 컨텐츠가 늘어나면 스크롤 안 됨
- **해결**:
  ```tsx
  <div className="h-screen flex flex-col overflow-hidden">
    <header>Fixed</header>
    <main className="flex-1 min-h-0 flex">  {/* min-h-0 필수! */}
      <aside className="flex flex-col">
        <div className="flex-1 min-h-0 overflow-y-auto">
          {/* 스크롤 가능한 영역 */}
        </div>
      </aside>
    </main>
  </div>
  ```

### Recording Flow (LiveKit Egress - 서버 녹음)
1. 첫 참여자 입장 시 Backend에서 자동 녹음 시작 (Room Composite Egress)
2. LiveKit Egress가 모든 참여자 오디오를 합성하여 녹음
3. 마지막 참여자 퇴장 시 Backend에서 녹음 중지
4. egress_ended 웹훅으로 파일 경로 수신, STT 작업 큐잉
5. MinIO에 직접 저장 (클라이언트 업로드 불필요)


### Client VAD (Voice Activity Detection) Pattern
- **위치**: `frontend/src/hooks/useVAD.ts`
- **라이브러리**: `@ricky0123/vad-web` (Silero VAD, ONNX 기반)
- **인터페이스**: `startVAD(stream)`, `stopVAD() -> VADMetadata`, `isListening`, `isSpeaking`
- **VADSegment**: `{ startMs, endMs }` - 발화 구간 정보
- **Backend 처리 우선순위**: 클라이언트 VAD -> 서버 VAD (webrtcvad) -> 전체 파일 STT
- **장점**: 서버 VAD 부하 제거, 클라이언트 실시간 발화 상태 UI 표시

### Recording Download Pattern
- **위치**: `frontend/src/components/meeting/RecordingList.tsx`
- **상태별 다운로드 가능 여부**:
  - `completed`: Audio 다운로드 가능
  - `transcribed`: Audio + Transcript 다운로드 가능
- **다운로드 버튼**:
  - **Audio**: `recordingService.downloadFile()` -> Blob -> .webm 파일
  - **Transcript**: `recording.transcriptText` -> Blob -> .txt 파일
- **패턴**:
  ```typescript
  // Audio 다운로드 (completed || transcribed)
  const blob = await recordingService.downloadFile(meetingId, recordingId);
  const url = URL.createObjectURL(blob);
  // ... 다운로드 링크 생성

  // Transcript 다운로드 (transcribed만)
  const blob = new Blob([recording.transcriptText], { type: 'text/plain;charset=utf-8' });
  // ... 다운로드 링크 생성
  ```

### LocalStorage Caching Pattern
- **유틸리티**: `frontend/src/utils/audioSettingsStorage.ts`
- **스토어**: `frontend/src/stores/meetingRoomStore.ts`
- **저장 항목**: `mit-audio-settings` (마이크 게인, 디바이스 ID), `mit-remote-volumes` (참여자별 볼륨)
- **패턴**: 스토어 초기화 시 로드, setter 호출 시 저장, reset 시 캐시 유지
- **주의**: remoteVolumes는 참여자 퇴장 시에도 삭제 안 함 (재입장 시 복원)

### Remote Audio Component Pattern
- **위치**: `frontend/src/components/meeting/RemoteAudio.tsx`
- **역할**: 원격 참여자 오디오 재생 및 볼륨 조절
- **Web Audio API**: GainNode로 볼륨 조절 (0.0 ~ 2.0), `setSinkId()`로 출력 장치 선택
- **Props**: `stream`, `odId`, `outputDeviceId`, `volume`

### Transcript Display Pattern
- **위치**: `frontend/src/components/meeting/TranscriptSection.tsx`
- **역할**: 회의록 발화 목록 표시 (실제 시각 HH:MM:SS 포맷)
- **타입**: `Utterance` 타입은 `packages/shared-types/src/api.ts`에서 자동 생성

## Spotlight Service Patterns (src/app/)

### 3-Column Layout Pattern
- **위치**: `src/app/layouts/MainLayout.tsx`
- **구조**: 좌측 280px (LeftSidebar) + 중앙 flex-1 (SpotlightInput) + 우측 400px (PreviewPanel)
- **핵심**: `h-screen flex overflow-hidden`, 사이드바 `flex-shrink-0`

### Glassmorphism Design System
- **위치**: `src/index.css`, `tailwind.config.js`
- **핵심 클래스**: `.glass-card`, `.glass-sidebar`, `.glass-input`
- **효과**: `backdrop-filter: blur()`, `rgba()` 배경색
- **Tailwind 색상**: `mit-primary`, `mit-secondary`, `card-bg`, `glass`

### Spotlight Command System Pattern
- **스토어**: `commandStore.ts` - 입력/자동완성/히스토리 상태
- **서비스**: `agentService.ts` - 명령어 정규식 패턴 매칭
- **훅**: `useCommand.ts` - 명령어 실행 및 응답 처리 (modal/navigation/direct)

### Modal Store Pattern
- **위치**: `src/app/stores/meetingModalStore.ts`
- **패턴**: Zustand로 모달 상태 분리 (`isOpen`, `initialData`, `openModal`, `closeModal`)
- **장점**: 여러 위치에서 모달 열기 가능 (명령어, 버튼, 네비게이션)

### Preview Panel Pattern
- **위치**: `src/app/stores/previewStore.ts`
- **상태**: `type` ('meeting' | 'team' | 'search' | 'help'), `data`, `setPreview`, `clearPreview`

### framer-motion Animation Pattern
- **위치**: `src/app/components/spotlight/SpotlightInput.tsx`
- **패턴**: `<AnimatePresence>` + `<motion.div>` 로 페이드 인/아웃 (opacity, y)

### Constants Extraction Pattern
- **위치**: `src/app/constants/index.ts`
- **상수 예시**: `HISTORY_LIMIT`, `SUGGESTIONS_DISPLAY_LIMIT`, `STATUS_COLORS`, `API_DELAYS`

### Date Utils Pattern
- **위치**: `src/app/utils/dateUtils.ts`
- **함수**: `formatRelativeTime(date)` - 상대 시간, `formatDuration(startTime)` - Duration

### Conversation Mode Pattern
- **위치**: `src/app/stores/conversationStore.ts`
- **상태**: `isConversationActive`, `messages`, `pendingForm`, `layoutMode`
- **메시지 타입**: `user` (우측 정렬), `agent` (좌측 정렬), `system` (중앙 정렬)
- **Layout 모드**:
  - `fullscreen`: 전체 화면 채팅 (기본값, 모든 사이드바 숨김)
  - `center-only`: 중앙 영역만 채팅 (좌/우 사이드바 유지)
  - `center-right-merged`: 중앙+우측 병합 (좌측만 유지)
- **컴포넌트 구조**:
  ```
  ConversationContainer
  ├── ChatMessageList (자동 스크롤)
  │   ├── UserMessageBubble
  │   ├── AgentMessageBubble (폼/결과 포함)
  │   └── SystemMessageBubble
  └── ChatSpotlightInput (하단 고정)
  ```

### Zustand Closure 방지 패턴
- **문제**: async 콜백에서 Zustand 훅으로 destructure한 값은 콜백 생성 시점 값으로 고정
  ```typescript
  // Bad - isActive는 콜백 생성 시점 값 (closure 캡처)
  const { isConversationActive } = useConversationStore();
  const handleSubmit = async () => {
    // ... async operation
    if (isConversationActive) { /* 항상 false일 수 있음 */ }
  };
  ```
- **해결**: `store.getState()`로 실행 시점에 최신 상태 조회
  ```typescript
  const handleSubmit = async () => {
    // ... async operation
    const { isConversationActive } = useConversationStore.getState();
    if (isConversationActive) { /* 최신 값 사용 */ }
  };
  ```
- **적용 위치**: `src/app/hooks/useCommand.ts`, `src/app/hooks/useConversationCommand.ts`

### Chat Bubble Animation Pattern
- **위치**: `src/app/constants/animations.ts`
- **Framer Motion variants**:
  ```typescript
  // 사용자 메시지: 오른쪽에서 슬라이드
  userMessage: { initial: { x: 20, opacity: 0 }, animate: { x: 0, opacity: 1 } }

  // 에이전트 메시지: 왼쪽에서 슬라이드
  agentMessage: { initial: { x: -20, opacity: 0 }, animate: { x: 0, opacity: 1 } }
  ```
- **Glass Morphism 버블 스타일**: `glass-card` 클래스 적용

### Chat Bubble Markdown Rendering Pattern
- **위치**: `src/app/components/conversation/AgentMessageBubble.tsx`
- **용도**: 에이전트 응답에서 마크다운 콘텐츠를 채팅 버블 내에서 렌더링
- **조건**: `agentData.responseType === 'result' && agentData.previewData?.content`
- **컴포넌트**: `MarkdownRenderer` (src/components/ui/MarkdownRenderer.tsx) 재사용
- **스타일**: `.chat-bubble-markdown` 클래스 (src/index.css)
  - 어두운 배경에 맞는 밝은 텍스트 색상
  - h2: 하단 보더 구분선, h3: mit-primary 색상 강조
  - 리스트 마커: mit-primary 색상
  - 코드, 인용문, 링크 등 스타일 포함
- **패턴**:
  ```tsx
  {agentData?.responseType === 'result' && agentData.previewData?.content ? (
    <MarkdownRenderer
      content={agentData.previewData.content}
      className="chat-bubble-markdown"
    />
  ) : (
    message.content && <p>{message.content}</p>
  )}
  ```

### Form State Consolidation Pattern
- **용도**: 여러 useState를 단일 formData 객체로 통합, `updateField<K>` 헬퍼 사용

### Type Guard Pattern
- **용도**: `as` 대신 런타임 타입 검증으로 안전한 타입 단언
- **패턴**: `isValidType(type): type is T { return VALID_TYPES.includes(type) }`

### Utility Extraction Pattern (DRY)
- **위치**: `src/app/utils/previewUtils.ts`, `src/app/utils/historyUtils.ts`
- **용도**: 여러 훅에서 중복되는 로직을 공유 유틸리티로 추출
- **패턴**:
  ```typescript
  // previewUtils.ts - 프리뷰 검증 및 업데이트
  export const VALID_PREVIEW_TYPES: PreviewType[] = [
    'meeting', 'document', 'command-result', ...
  ];
  export function isValidPreviewType(type: string): type is PreviewType {
    return VALID_PREVIEW_TYPES.includes(type as PreviewType);
  }
  export function updatePreviewStore(
    setPreview: (type: PreviewType, data: PreviewDataOutput) => void,
    input: PreviewDataInput
  ): void { /* ... */ }

  // historyUtils.ts - 히스토리 아이템 생성
  export function createSuccessHistoryItem(command: string, result: string, icon?: string): HistoryItem
  export function createErrorHistoryItem(command: string, result?: string): HistoryItem
  ```
- **적용 위치**: `useCommand.ts`, `useConversationCommand.ts`

### Strategy Pattern for Command Matching
- **위치**: `src/app/services/commandMatcher.ts`
- **용도**: 명령어 매칭 로직을 데이터 중심 패턴으로 분리 (cyclomatic complexity 감소)
- **패턴**:
  ```typescript
  interface CommandPattern {
    keywords: string[];
    excludeKeywords?: string[];
    response: keyof typeof MOCK_RESPONSES;
    condition?: (command: string, context?: SessionContext | null) => boolean;
  }

  const COMMAND_PATTERNS: CommandPattern[] = [
    { keywords: ['회의', '미팅'], condition: (cmd) => cmd.includes('시작'), response: 'meeting_create' },
    { keywords: ['검색', '찾'], response: 'search' },
    { keywords: ['일정', '스케줄', '오늘'], response: 'schedule' },
    // ... 패턴 추가 시 여기에만 추가
  ];

  export function matchCommand(command: string, context?: SessionContext | null): MockResponse
  ```
- **장점**:
  - if-else 분기 대신 선언적 패턴 배열
  - 새 명령어 추가 시 패턴 배열에만 추가
  - 테스트 용이 (각 패턴 독립적)

### Mock Data Separation Pattern
- **위치**: `src/app/services/mockResponses.ts`
- **용도**: 비즈니스 로직(agentService)에서 Mock 데이터 분리
- **패턴**:
  ```typescript
  // mockResponses.ts - 데이터 정의만
  export interface MockResponse {
    type: 'form' | 'direct' | 'modal';
    tool?: AgentTool;
    title?: string;
    fields?: CommandField[];
    // ...
  }
  export const MOCK_RESPONSES: Record<string, MockResponse> = { ... };

  // agentService.ts - 비즈니스 로직만
  import { matchCommand } from './commandMatcher';
  const matched = matchCommand(command, context);
  // 응답 타입별 처리 ...
  ```
- **장점**:
  - 단일 책임 원칙 (데이터 vs 로직)
  - agentService 384 lines -> ~146 lines
  - Mock -> 실제 API 전환 시 agentService만 수정

### useRef for Persistent State Pattern
- **용도**: UI 렌더링에 영향 없는 값 (타이머 시작 시간 등)은 useRef 사용
- **주의**: UI에 반영해야 하는 값은 useState 사용

### Section Component Extraction Pattern
- **용도**: 반복되는 스타일/구조를 작은 컴포넌트로 추출

## Backend Patterns

> **상세 Backend 패턴 및 ADR**: `backend/CLAUDE-patterns.md`, `backend/CLAUDE-decisions.md` 참조

### Redis Client Singleton Pattern
- **위치**: `backend/app/core/redis.py`
- **패턴**:
  ```python
  import redis.asyncio as redis
  from app.core.config import get_settings

  _redis_client: redis.Redis | None = None

  async def get_redis() -> redis.Redis:
      global _redis_client
      if _redis_client is None:
          settings = get_settings()
          _redis_client = redis.from_url(settings.redis_url)
      return _redis_client
  ```
- **사용**: `redis = await get_redis()`

### LiveKit Webhook Signature Verification Pattern
- **위치**: `backend/app/api/v1/endpoints/livekit_webhooks.py`
- **패턴**:
  ```python
  from livekit import api
  from google.protobuf.json_format import MessageToDict

  async def verify_and_parse_webhook(request: Request, authorization: str) -> dict | None:
      # 1. TokenVerifier 생성
      token_verifier = api.TokenVerifier(api_key, api_secret)

      # 2. WebhookReceiver에 전달
      webhook_receiver = api.WebhookReceiver(token_verifier)

      # 3. 서명 검증 + 이벤트 파싱
      event = webhook_receiver.receive(body.decode(), authorization)

      # 4. Protobuf -> dict 변환 (camelCase 필드명!)
      return MessageToDict(event, preserving_proto_field_name=False)
  ```
- **주의**:
  - `preserving_proto_field_name=False` 필수 (egressInfo, roomName 등 camelCase)
  - `True`로 설정하면 egress_info, room_name 등 snake_case 출력

### Egress State Management Pattern (Redis)
- **위치**: `backend/app/services/livekit_service.py`
- **패턴**:
  ```python
  EGRESS_KEY_PREFIX = "livekit:egress:"
  EGRESS_TTL_SECONDS = 86400  # 24시간

  async def _set_active_egress(self, meeting_id: UUID, egress_id: str):
      redis = await get_redis()
      await redis.set(f"{EGRESS_KEY_PREFIX}{meeting_id}", egress_id, ex=EGRESS_TTL_SECONDS)

  async def _get_active_egress(self, meeting_id: UUID) -> str | None:
      redis = await get_redis()
      result = await redis.get(f"{EGRESS_KEY_PREFIX}{meeting_id}")
      return result.decode() if result else None

  async def clear_active_egress(self, meeting_id: UUID):
      redis = await get_redis()
      await redis.delete(f"{EGRESS_KEY_PREFIX}{meeting_id}")
  ```
- **웹훅에서 정리**: egress_ended 이벤트 시 모든 종료 상태(COMPLETE/FAILED/ABORTED)에서 호출

## API Contract Patterns

### Schema File Structure
```
api-contract/
├── openapi.yaml           # 메인 진입점 ($ref 집합)
├── schemas/
│   ├── common.yaml        # 공통 타입 (UUID, Timestamp, ErrorResponse, PaginationMeta)
│   ├── auth.yaml          # 인증 스키마
│   ├── team.yaml          # 팀 + 팀멤버 스키마
│   ├── meeting.yaml       # 회의 + 참여자 스키마
│   ├── webrtc.yaml        # WebRTC 스키마
│   └── recording.yaml     # 녹음 스키마
└── paths/
    └── *.yaml             # 엔드포인트 정의
```

### Reference Patterns
- **paths -> schemas**: `$ref: '../schemas/team.yaml#/components/schemas/Team'`
- **schemas 내부 참조**: `$ref: '#/components/schemas/TeamRole'`
- **common types 사용**: UUID, Timestamp는 항상 common.yaml에서 참조

### List Response Pattern
```yaml
# 모든 목록 응답은 이 패턴 준수
SomeListResponse:
  type: object
  required:
    - items
    - meta
  properties:
    items:
      type: array
      items:
        $ref: '#/components/schemas/SomeItem'
    meta:
      $ref: './common.yaml#/components/schemas/PaginationMeta'
```

### Schema Extension Pattern (allOf)
```yaml
# 기본 스키마 확장 시 allOf 사용
TeamWithMembers:
  allOf:
    - $ref: '#/components/schemas/Team'
    - type: object
      required:
        - members
      properties:
        members:
          type: array
          items:
            $ref: '#/components/schemas/TeamMember'
```

## Naming Conventions & File Organization

> **CLAUDE.md** 의 "Naming Conventions", "Architecture" 섹션 참조

## Docker Configuration Patterns

### LiveKit Config Inline Pattern
- **위치**: `docker/docker-compose.yml`
- **용도**: docker-compose의 `${VAR}` 치환을 활용한 설정 전달
- **패턴**:
  ```yaml
  # LiveKit 서버 설정 (LIVEKIT_CONFIG)
  livekit:
    environment:
      LIVEKIT_CONFIG: |
        port: 7880
        keys:
          ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
        redis:
          address: redis:6379

  # LiveKit Egress 설정 (EGRESS_CONFIG_BODY)
  livekit-egress:
    environment:
      EGRESS_CONFIG_BODY: |
        api_key: ${LIVEKIT_API_KEY}
        api_secret: ${LIVEKIT_API_SECRET}
        ws_url: ws://livekit:7880
        redis:
          address: redis:6379
        s3:
          access_key: ${MINIO_ROOT_USER:-minioadmin}
          secret: ${MINIO_ROOT_PASSWORD:-minioadmin}
          endpoint: http://minio:9000
          bucket: recordings
          force_path_style: true
  ```
- **주의**:
  - `EGRESS_CONFIG_FILE` + 파일 마운트보다 인라인 설정이 더 안정적
  - `REDIS_ADDRESS` 환경변수는 Egress에서 지원 안 됨 (config에 직접 설정)
  - depends_on에 healthcheck 조건 추가 권장

### nginx WebSocket Proxy Pattern
- **위치**: `frontend/nginx.conf`
- **용도**: LiveKit WebSocket 연결 프록시
- **패턴**:
  ```nginx
  location /livekit/ {
      proxy_pass http://livekit:7880/;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;

      # 장시간 WebSocket 연결 유지 (회의 중 연결 끊김 방지)
      proxy_connect_timeout 7d;
      proxy_send_timeout 7d;
      proxy_read_timeout 7d;
  }
  ```
- **주의**:
  - `proxy_http_version 1.1` 필수 (HTTP/1.1 WebSocket 업그레이드)
  - `Connection "upgrade"` 필수 (WebSocket 핸드셰이크)
  - 타임아웃은 충분히 길게 설정 (회의 시간 고려)

### TURN TLS Certificate Pattern
- **위치**: `docker/docker-compose.yml`
- **용도**: NAT/방화벽 환경에서 WebRTC 연결 성공률 향상 (85% -> 99%+)
- **인증서**: Let's Encrypt + certbot
- **패턴**:
  ```yaml
  livekit:
    ports:
      - "5349:5349"       # TURN TLS
      - "3478:3478/udp"   # TURN UDP
    volumes:
      # 심볼릭 링크 유지를 위해 전체 디렉토리 마운트
      - /etc/letsencrypt:/etc/letsencrypt:ro
    environment:
      LIVEKIT_CONFIG: |
        turn:
          enabled: true
          domain: ${LIVEKIT_TURN_DOMAIN:-}
          tls_port: 5349
          udp_port: 3478
          cert_file: /etc/letsencrypt/live/turn.mit-hub.com/fullchain.pem
          key_file: /etc/letsencrypt/live/turn.mit-hub.com/privkey.pem
  ```
- **인증서 발급**:
  ```bash
  # 1. DNS A 레코드 추가 (turn.example.com -> 서버 IP)
  # 2. certbot 설치 및 인증서 발급
  sudo certbot certonly --standalone -d turn.example.com
  # 3. 권한 설정 (Docker에서 읽기 위해)
  sudo chmod 755 /etc/letsencrypt/{live,archive}
  sudo chmod 644 /etc/letsencrypt/archive/turn.example.com/privkey1.pem
  ```
- **주의**:
  - Let's Encrypt는 `live/` -> `archive/` 심볼릭 링크 사용
  - 개별 디렉토리 마운트 시 심볼릭 링크 깨짐
  - 전체 `/etc/letsencrypt` 마운트 필수
  - `privkey.pem`은 기본 600 권한 -> Docker에서 읽으려면 644 필요
- **환경변수**:
  ```bash
  # docker/.env
  LIVEKIT_TURN_DOMAIN=turn.mit-hub.com
  ```
