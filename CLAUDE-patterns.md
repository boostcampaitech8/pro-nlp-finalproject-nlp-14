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
- **인터페이스**:
  ```typescript
  interface UseLiveKitReturn {
    // 연결 상태
    connectionState: ConnectionState;
    participants: Map<string, RoomParticipant>;
    error: string | null;

    // 미디어 스트림
    localStream: MediaStream | null;
    remoteStreams: Map<string, MediaStream>;
    isAudioMuted: boolean;

    // 오디오 설정 (localStorage 캐싱)
    audioInputDeviceId: string | null;
    audioOutputDeviceId: string | null;
    micGain: number;
    remoteVolumes: Map<string, number>;

    // 화면공유
    isScreenSharing: boolean;
    screenStream: MediaStream | null;
    remoteScreenStreams: Map<string, MediaStream>;

    // 녹음 (서버 측)
    isRecording: boolean;
    isUploading: boolean;

    // 채팅
    chatMessages: ChatMessage[];

    // 액션
    joinRoom: (userId: string) => Promise<void>;
    leaveRoom: () => Promise<void>;
    toggleMute: () => void;
    forceMute: (targetUserId: string, muted: boolean) => void;
    changeAudioInputDevice: (deviceId: string) => Promise<void>;
    changeAudioOutputDevice: (deviceId: string) => void;
    changeMicGain: (gain: number) => void;
    changeRemoteVolume: (userId: string, volume: number) => void;
    startScreenShare: () => Promise<void>;
    stopScreenShare: () => void;
    sendChatMessage: (content: string) => void;
  }
  ```
- **핵심 패턴**:
  ```typescript
  // Room 생성 (rtcConfig는 여기에 포함하지 않음)
  const room = new Room({
    adaptiveStream: true,
    dynacast: true,
  });
  const token = await fetchToken(meetingId, userId);

  // Room 연결 (rtcConfig는 connect()에 전달)
  await room.connect(wsUrl, token, {
    rtcConfig: {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
      ],
      iceTransportPolicy: 'all', // TURN 필요시 'relay'
    },
  });

  // 로컬 오디오 퍼블리시
  const tracks = await createLocalTracks({ audio: true, video: false });
  await room.localParticipant.publishTrack(tracks[0]);

  // 원격 트랙 구독 (자동)
  room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === Track.Kind.Audio) {
      const stream = new MediaStream([track.mediaStreamTrack]);
      setRemoteStreams(prev => new Map(prev).set(participant.identity, stream));
    }
  });

  // DataPacket 전송 (채팅, VAD, 강제 음소거)
  room.localParticipant.publishData(
    new TextEncoder().encode(JSON.stringify({ type: 'chat', content })),
    { reliable: true }
  );
  ```
- **Web Audio 통합**:
  ```typescript
  // 마이크 게인 조절
  const gainNode = audioContext.createGain();
  gainNode.gain.value = micGain;
  source.connect(gainNode).connect(destination);

  // 원격 볼륨 조절 (RemoteAudio 컴포넌트에서)
  const remoteGain = audioContext.createGain();
  remoteGain.gain.value = remoteVolumes.get(odId) ?? 1.0;
  ```
- **localStorage 캐싱**: 마이크 게인, 디바이스 설정, 참여자별 볼륨 유지


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
- **구조**:
  ```typescript
  export interface VADSegment {
    startMs: number;  // 발화 시작 시간 (녹음 시작 기준)
    endMs: number;    // 발화 종료 시간
  }

  export interface VADMetadata {
    segments: VADSegment[];
    totalDurationMs: number;
    settings: { positiveSpeechThreshold, minSpeechFrames, ... };
  }

  export function useVAD(options): {
    isListening: boolean;
    isSpeaking: boolean;
    currentSegments: VADSegment[];
    vadMetadata: VADMetadata | null;
    startVAD(stream: MediaStream): void;
    stopVAD(): VADMetadata;
    resetVAD(): void;
  }
  ```
- **통합 (useRecording.ts)**:
  ```typescript
  // VAD 시작: MediaRecorder 시작과 함께
  const startRecording = async () => {
    mediaRecorderRef.current.start();
    startVAD(localStream);  // VAD 동시 시작
  };

  // VAD 종료: 업로드 전 메타데이터 캡처
  const stopRecording = async () => {
    const vadMeta = stopVAD();
    await uploadRecording({ ...params, vadMetadata: vadMeta });
  };
  ```
- **Backend 처리 (stt_service.py)**:
  ```python
  # 클라이언트 VAD 우선 사용 -> 서버 VAD 폴백 -> 전체 파일 STT
  if has_client_vad:
      return await self._transcribe_with_client_vad(...)
  elif use_vad:
      return await self._transcribe_with_vad(...)  # 서버 VAD
  else:
      return await provider.transcribe(file_data)
  ```
- **장점**:
  - 서버 VAD 분석 부하 제거 (webrtcvad 처리 불필요)
  - 클라이언트에서 실시간 발화 상태 UI 표시 가능
  - 녹음 중 발화 구간 수 표시 가능 (vadSegmentCount)

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
- **유틸리티 위치**: `frontend/src/utils/audioSettingsStorage.ts`
- **스토어 위치**: `frontend/src/stores/meetingRoomStore.ts`
- **용도**: 사용자 설정을 회의 간 유지
- **저장 항목**:
  - `mit-audio-settings`: 마이크 게인, 입/출력 디바이스 ID
  - `mit-remote-volumes`: 참여자별 볼륨 설정 (userId -> volume)
- **유틸리티 함수**:
  ```typescript
  // utils/audioSettingsStorage.ts
  export function loadAudioSettings(): Partial<AudioSettings> { ... }
  export function saveAudioSettings(settings: AudioSettings): void { ... }
  export function loadRemoteVolumes(): Map<string, number> { ... }
  export function saveRemoteVolumes(volumes: Map<string, number>): void { ... }
  ```
- **스토어 패턴**:
  ```typescript
  // 로드 (스토어 초기화 시)
  const cachedSettings = loadAudioSettings();
  const initialState = {
    micGain: cachedSettings.micGain ?? 1.0,
    ...
  };

  // 저장 (setter 함수에서)
  setMicGain: (micGain) => {
    set({ micGain });
    saveAudioSettings({ micGain, ... });
  },

  // 리셋 시 캐시 유지
  reset: () => {
    const { micGain, remoteVolumes, ... } = get();
    set({ ...initialState, micGain, remoteVolumes });
  }
  ```
- **주의**: remoteVolumes는 참여자 퇴장 시에도 삭제하지 않음 (재입장 시 복원)

### Remote Audio Component Pattern
- **위치**: `frontend/src/components/meeting/RemoteAudio.tsx`
- **역할**: 원격 참여자 오디오 재생 및 볼륨 조절
- **패턴**:
  ```typescript
  // Web Audio API GainNode로 볼륨 조절 (0.0 ~ 2.0 범위)
  const audioContext = new AudioContext();
  const source = audioContext.createMediaStreamSource(stream);
  const gainNode = audioContext.createGain();
  gainNode.gain.value = volume;
  source.connect(gainNode);
  gainNode.connect(audioContext.destination);

  // setSinkId로 출력 장치 선택
  audioElement.setSinkId(outputDeviceId);
  ```
- **Props**: `stream`, `odId`, `outputDeviceId`, `volume`

### Transcript Display Pattern
- **위치**: `frontend/src/components/meeting/TranscriptSection.tsx`
- **역할**: 회의록 발화 목록 표시 (실제 시각 포함)
- **패턴**:
  ```typescript
  // 실제 발화 시각 포맷팅 (HH:MM:SS)
  function formatTimestamp(timestamp: string | null | undefined): string {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
  }

  // 발화 목록 렌더링
  {transcript.utterances.map((utterance) => (
    <div key={utterance.id} className="flex gap-3">
      <div className="flex-shrink-0 w-24">
        <span className="text-xs text-gray-400">
          {formatTimestamp(utterance.timestamp)}  // 실제 시각
        </span>
      </div>
      <div className="flex-1">
        <span className="font-medium text-blue-600">
          [{utterance.speakerName}]
        </span>
        <span className="text-gray-700">{utterance.text}</span>
      </div>
    </div>
  ))}
  ```
- **타입**: `Utterance` 타입은 `packages/shared-types/src/api.ts`에서 자동 생성 (OpenAPI 스키마 기반)

## Spotlight Service Patterns (src/app/)

### 3-Column Layout Pattern
- **위치**: `src/app/layouts/MainLayout.tsx`
- **구조**:
  ```tsx
  <div className="h-screen flex gradient-bg overflow-hidden">
    {/* 좌측 사이드바 - 280px 고정 */}
    <aside className="w-[280px] flex-shrink-0 glass-sidebar">
      <LeftSidebar />
    </aside>

    {/* 중앙 컨텐츠 - flex-1 */}
    <main className="flex-1 flex flex-col min-h-0">
      <SpotlightInput />
      <div className="flex-1 overflow-y-auto">
        {/* 컨텐츠 */}
      </div>
    </main>

    {/* 우측 사이드바 - 400px 고정 */}
    <aside className="w-[400px] flex-shrink-0">
      <PreviewPanel />
    </aside>
  </div>
  ```

### Glassmorphism Design System
- **위치**: `src/index.css`
- **핵심 클래스**:
  ```css
  /* 글래스 카드 */
  .glass-card {
    @apply bg-card-bg backdrop-blur-lg border border-glass rounded-xl;
  }

  /* 글래스 사이드바 */
  .glass-sidebar {
    background: rgba(15, 23, 42, 0.8);
    backdrop-filter: blur(40px) saturate(150%);
  }

  /* 글래스 입력창 */
  .glass-input {
    @apply bg-input-bg backdrop-blur-xl border-2 border-glass-light rounded-2xl;
  }
  ```
- **Tailwind 확장** (tailwind.config.js):
  ```javascript
  colors: {
    'mit-primary': '#3b82f6',
    'mit-secondary': '#8b5cf6',
    'card-bg': 'rgba(255, 255, 255, 0.03)',
    'glass': 'rgba(255, 255, 255, 0.08)',
  }
  ```

### Spotlight Command System Pattern
- **스토어**: `src/app/stores/commandStore.ts`
- **서비스**: `src/app/services/agentService.ts`
- **훅**: `src/app/hooks/useCommand.ts`
- **구조**:
  ```typescript
  // commandStore.ts - 상태 관리
  interface CommandState {
    input: string;
    suggestions: CommandSuggestion[];
    history: CommandHistoryItem[];
    isProcessing: boolean;
    setInput: (input: string) => void;
    addToHistory: (item: CommandHistoryItem) => void;
  }

  // agentService.ts - 명령어 매칭
  const COMMAND_PATTERNS: CommandPattern[] = [
    { pattern: /^회의\s*(시작|생성|만들기)/, command: 'meeting_create', ... },
    { pattern: /^팀\s*(목록|리스트)/, command: 'team_list', ... },
  ];

  // useCommand.ts - 훅
  function useCommand() {
    const handleSubmit = async (input: string) => {
      const response = await agentService.processCommand(input);
      if (response.type === 'modal') {
        openMeetingModal(response.modalData);
      } else if (response.type === 'navigation') {
        navigate(response.path);
      }
    };
  }
  ```

### Modal Store Pattern
- **위치**: `src/app/stores/meetingModalStore.ts`
- **패턴**: Zustand 기반 모달 상태 분리
- **구조**:
  ```typescript
  interface MeetingModalState {
    isOpen: boolean;
    initialData: MeetingModalData | null;
    openModal: (data?: MeetingModalData) => void;
    closeModal: () => void;
  }

  // 사용
  const { openModal } = useMeetingModalStore();
  openModal({ title: '새 회의', teamId: 'xxx' });
  ```
- **장점**:
  - 모달 상태와 트리거 분리
  - 여러 위치에서 모달 열기 가능 (명령어, 버튼, 네비게이션)

### Preview Panel Pattern
- **위치**: `src/app/stores/previewStore.ts`
- **역할**: 우측 사이드바 미리보기 컨텐츠 관리
- **구조**:
  ```typescript
  interface PreviewState {
    type: 'none' | 'meeting' | 'team' | 'search' | 'help';
    data: PreviewData | null;
    setPreview: (type: PreviewType, data?: PreviewData) => void;
    clearPreview: () => void;
  }
  ```

### framer-motion Animation Pattern
- **위치**: `src/app/components/spotlight/SpotlightInput.tsx`
- **패턴**:
  ```tsx
  import { motion, AnimatePresence } from 'framer-motion';

  // 페이드 인/아웃
  <AnimatePresence>
    {suggestions.length > 0 && (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.15 }}
      >
        {/* 자동완성 목록 */}
      </motion.div>
    )}
  </AnimatePresence>
  ```

### Constants Extraction Pattern
- **위치**: `src/app/constants/index.ts`
- **용도**: 매직 넘버, 반복 설정값 중앙 관리
- **패턴**:
  ```typescript
  // constants/index.ts
  export const HISTORY_LIMIT = 50;
  export const SUGGESTIONS_DISPLAY_LIMIT = 4;

  export const STATUS_COLORS = {
    success: 'bg-mit-success/20 text-mit-success',
    error: 'bg-mit-warning/20 text-mit-warning',
    pending: 'bg-mit-primary/20 text-mit-primary',
  } as const;

  export const API_DELAYS = {
    COMMAND_PROCESS: 500,
    FORM_SUBMIT: 800,
    SUGGESTIONS_FETCH: 200,
  } as const;

  // 사용
  import { HISTORY_LIMIT, STATUS_COLORS } from '@/app/constants';
  history.slice(0, HISTORY_LIMIT);
  ```

### Date Utils Pattern
- **위치**: `src/app/utils/dateUtils.ts`
- **용도**: 날짜/시간 포맷팅 함수 재사용
- **패턴**:
  ```typescript
  // 상대 시간 (방금 전, 5분 전, 2시간 전)
  export function formatRelativeTime(date: Date): string;

  // Duration (1:30:45, 5:30)
  export function formatDuration(startTime: Date): string;
  ```

### Form State Consolidation Pattern
- **위치**: `src/app/components/meeting/MeetingModal.tsx`
- **용도**: 여러 useState를 단일 객체로 통합하여 re-render 최적화
- **패턴**:
  ```typescript
  // Before: 5개 useState - 각각 re-render 유발
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  // ...

  // After: 단일 formData 객체
  interface FormData {
    title: string;
    description: string;
    scheduledAt: string;
    teamId: string;
  }

  const [formData, setFormData] = useState<FormData>(initialFormData);

  // 헬퍼 함수로 필드 업데이트
  const updateField = <K extends keyof FormData>(field: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  // 사용
  <Input value={formData.title} onChange={(e) => updateField('title', e.target.value)} />
  ```

### Type Guard Pattern
- **위치**: `src/app/hooks/useCommand.ts`
- **용도**: 런타임 타입 검증으로 안전한 타입 단언
- **패턴**:
  ```typescript
  // 유효한 타입 목록 정의
  const VALID_PREVIEW_TYPES: PreviewType[] = ['meeting', 'document', 'command-result', 'search-result'];

  // 타입 가드 함수
  function isValidPreviewType(type: string): type is PreviewType {
    return VALID_PREVIEW_TYPES.includes(type as PreviewType);
  }

  // 사용 - as 대신 타입 가드
  if (isValidPreviewType(response.previewData.type)) {
    setPreview(response.previewData.type, data);  // 안전하게 타입 추론
  } else {
    console.warn(`Unknown preview type: ${response.previewData.type}`);
    setPreview('command-result', data);  // 폴백
  }
  ```

### useRef for Persistent State Pattern
- **위치**: `src/app/components/sidebar/LeftSidebar.tsx`
- **용도**: re-render에도 유지해야 하는 값 (타이머 시작 시간 등)
- **패턴**:
  ```typescript
  // Before: useState - re-render마다 초기화
  const [startTime] = useState<Date | null>(null);

  // After: useRef - re-render에도 값 유지
  const startTimeRef = useRef<Date | null>(null);

  useEffect(() => {
    if (shouldStart && !startTimeRef.current) {
      startTimeRef.current = new Date();
    }
    // startTimeRef.current는 의존성 배열에 불필요
  }, [shouldStart]);
  ```
- **주의**: UI에 반영해야 하는 값은 useState 사용, 내부 로직에만 필요한 값은 useRef

### Section Component Extraction Pattern
- **위치**: `src/app/components/sidebar/Navigation.tsx`
- **용도**: 반복되는 스타일/구조 컴포넌트화
- **패턴**:
  ```typescript
  // 반복되는 섹션 타이틀 추출
  function SectionTitle({ children }: { children: React.ReactNode }) {
    return <p className="text-nav-title px-3 mb-2">{children}</p>;
  }

  // 사용
  <SectionTitle>Main</SectionTitle>
  <SectionTitle>Teams</SectionTitle>
  <SectionTitle>System</SectionTitle>
  ```

## Backend Patterns

### API Structure
```
backend/app/
├── api/v1/endpoints/  # 라우터
├── services/          # 비즈니스 로직
├── models/            # SQLAlchemy 모델
├── schemas/           # Pydantic 스키마
└── core/              # 설정, 보안, DB
```

### Recording Upload (Presigned URL)
1. `POST /recordings/upload-url` - URL 발급 + DB 레코드 생성 (pending)
2. 클라이언트가 MinIO에 직접 PUT
3. `POST /recordings/{id}/confirm` - 파일 확인 + 상태 변경 (completed)

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

## Naming Conventions

| 영역 | 규칙 | 예시 |
|------|------|------|
| API 경로 | kebab-case | `/api/v1/meeting-reviews` |
| DB 테이블/컬럼 | snake_case | `meeting_recordings`, `created_at` |
| TypeScript 변수 | camelCase | `meetingId`, `isRecording` |
| TypeScript 타입 | PascalCase | `MeetingRoom`, `RecordingStatus` |
| Python 변수/함수 | snake_case | `meeting_id`, `get_recording` |
| Python 클래스 | PascalCase | `MeetingRecording`, `ConnectionManager` |

## File Organization

### Frontend Hooks
```
hooks/
├── useLiveKit.ts          # LiveKit SFU 연결, 미디어 관리, 채팅, 녹음 (핵심)
├── useVAD.ts              # 클라이언트 VAD (Silero VAD, ONNX)
└── useAudioDevices.ts     # 오디오 디바이스 선택
```
**참고**: 레거시 Mesh P2P 훅 (useWebRTC, useSignaling, usePeerConnections) 삭제됨

### Frontend Components
```
components/
├── meeting/
│   ├── MeetingRoom.tsx         # 메인 회의 UI (접이식 사이드바)
│   ├── RemoteAudio.tsx         # 원격 오디오 재생 (Web Audio GainNode)
│   ├── AudioControls.tsx       # 오디오 컨트롤 (음소거, 게인)
│   ├── DeviceSelector.tsx      # 디바이스 선택 드롭다운
│   ├── VolumeSlider.tsx        # 볼륨 슬라이더
│   ├── ParticipantList.tsx     # 참여자 목록 + Force Mute
│   ├── ParticipantSection.tsx  # 참여자 섹션 (다중 선택 추가)
│   ├── RecordingList.tsx       # 녹음 목록 (MeetingDetailPage용)
│   ├── MeetingInfoCard.tsx     # 회의 정보 카드
│   ├── ChatPanel.tsx           # 채팅 패널 (Markdown, 연속 메시지)
│   └── ScreenShareView.tsx     # 화면공유 뷰
├── team/
│   ├── TeamInfoCard.tsx        # 팀 정보 카드
│   ├── TeamMemberSection.tsx   # 팀 멤버 섹션
│   └── MeetingListSection.tsx  # 회의 목록 섹션
├── ui/
│   └── MarkdownRenderer.tsx    # Markdown 렌더링 (react-markdown)
utils/
├── audioSettingsStorage.ts     # localStorage 오디오 설정 캐싱
└── ...
```

### Backend Services
```
services/
├── auth_service.py          # 인증 (JWT)
├── team_service.py          # 팀 CRUD
├── meeting_service.py       # 회의 CRUD
├── livekit_service.py       # LiveKit 토큰 생성, Room Composite Egress 녹음 관리
├── vad_event_service.py     # VAD 이벤트 처리 (DataPacket 수신)
├── recording_service.py     # 녹음 업로드/다운로드
├── stt_service.py           # STT 변환 로직
├── transcript_service.py    # 회의록 병합/관리 (wall-clock timestamp 기반)
├── chat_service.py          # 채팅 메시지 CRUD
└── stt/
    ├── base.py              # STTProvider 추상 클래스
    ├── openai_provider.py   # OpenAI Whisper 구현
    └── factory.py           # Provider 팩토리
```
**참고**: 레거시 signaling_service.py 삭제됨 (LiveKit으로 대체)

## STT (Speech-to-Text) Patterns

### Provider Abstraction
```python
# 확장 가능한 STT Provider 패턴
class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: str = "ko") -> TranscriptionResult:
        pass

# 팩토리로 Provider 생성
provider = STTProviderFactory.create("openai")  # 또는 "local", "self_hosted"
```

### ARQ Worker Pattern
```python
# 비동기 작업 큐 패턴 (arq_worker.py)
async def transcribe_meeting_task(ctx: dict, meeting_id: str, language: str = "ko"):
    async with async_session_maker() as db:
        service = TranscriptService(db)
        # 비동기 STT 처리
        ...

class WorkerSettings:
    functions = [transcribe_meeting_task, ...]
    redis_settings = RedisSettings(...)
```

### VAD Preprocessing
```python
# Voice Activity Detection으로 발화 구간만 추출
preprocessor = AudioPreprocessor()
segments = preprocessor.extract_speech_segments(audio_data)
# 무음 구간 제거 -> API 비용 절감
```

### Transcript Merge Pattern
```python
# 화자별 녹음을 wall-clock timestamp 기반으로 병합
# 각 녹음의 started_at + segment.startMs로 실제 시각 계산
for recording in transcribed_recordings:
    recording_start = recording.started_at  # 녹음 시작 시각 (datetime)

    for segment in recording.transcript_segments:
        start_ms = segment.get("startMs", 0)
        # 실제 발화 시각 계산
        absolute_timestamp = recording_start + timedelta(milliseconds=start_ms)

        utterance = Utterance(
            id=utterance_id,
            speaker_id=str(recording.user_id),
            speaker_name=user.name,
            start_ms=start_ms,
            end_ms=segment.get("endMs", 0),
            text=segment.get("text", ""),
            absolute_timestamp=absolute_timestamp,  # wall-clock time
        )
        all_utterances.append(utterance)

# 실제 시간 기준 정렬 (대화 맥락 명확화)
all_utterances.sort(key=lambda u: u.absolute_timestamp)

# JSON 저장 시 ISO 8601 형식
utterance.to_dict() -> {
    "id": 0,
    "speakerId": "uuid",
    "speakerName": "이름",
    "startMs": 0,
    "endMs": 1500,
    "text": "발화 내용",
    "timestamp": "2026-01-14T15:30:45.123456+00:00"
}
```

### Environment Variables (STT)
```bash
OPENAI_API_KEY=sk-xxx           # OpenAI API 키
STT_PROVIDER=openai             # openai, local, self_hosted
ARQ_REDIS_URL=redis://redis:6379/1  # Worker용 별도 Redis DB
```

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
