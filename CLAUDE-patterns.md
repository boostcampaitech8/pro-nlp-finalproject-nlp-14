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

### WebRTC Hook (useWebRTC)
- **위치**: `frontend/src/hooks/useWebRTC.ts`
- **역할**: WebRTC 연결, 시그널링, 녹음 관리 (통합 훅)
- **분리된 훅 구조**:
  ```
  hooks/
  ├── useWebRTC.ts           # 통합 훅 (다른 훅들 조합)
  ├── useSignaling.ts        # 시그널링 서버 연결/메시지
  ├── usePeerConnections.ts  # RTCPeerConnection 관리
  ├── useAudioDevices.ts     # 오디오 디바이스 선택
  ├── useScreenShare.ts      # 화면공유 관리
  └── useRecording.ts        # 녹음 관리
  ```
- **패턴**:
  - ref 사용으로 cleanup 시 최신 상태 참조
  - useCallback으로 함수 메모이제이션
  - 연결 시 자동 녹음 시작, 퇴장 시 업로드
  - cleanup useEffect는 `[]` dependency로 unmount 시에만 실행

### Audio Processing
- **GainNode**: 마이크 볼륨 조절 (0.0 ~ 2.0)
- **processedAudioRef**: Web Audio API로 처리된 스트림 관리
- **디바이스 선택**: useAudioDevices 훅으로 입/출력 장치 관리

### Chat System
- **위치**: `frontend/src/components/meeting/ChatPanel.tsx`
- **기능**:
  - WebSocket으로 실시간 메시지 전송/수신
  - DB 저장으로 히스토리 유지
  - 회의 입장 시 GET /meetings/{id}/chat으로 히스토리 로드
  - Markdown 렌더링 지원
  - 연속 메시지 그룹화 (같은 사람, 1분 이내)
  - Shift+Enter 줄바꿈, Enter 전송
- **Props**:
  - `hideHeader`: 헤더 숨김 (접이식 UI용)
  - `currentUserId`: 본인 메시지 구분

### Force Mute (Host 강제 음소거)
- **메시지 플로우**:
  ```
  Host -> force-mute(targetUserId, muted) -> Server
  Server -> force-muted(muted, byUserId) -> Target
  Server -> participant-muted(userId, muted) -> All
  ```
- **권한 검증**: `connection_manager.get_participant()` role 확인

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

### Recording Flow
1. 연결 시 MediaRecorder 자동 시작
2. 10초마다 IndexedDB에 증분 저장 (recordingStorageService)
3. 퇴장 시 Presigned URL로 MinIO 직접 업로드
4. beforeunload 시 localStorage 백업

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

### WebSocket Signaling
- **위치**: `backend/app/services/signaling_service.py`
- **패턴**: ConnectionManager 싱글톤으로 회의별 연결 관리
- **메시지 타입**: join, leave, offer, answer, ice-candidate, mute, screen-share-*

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
├── signaling_service.py     # WebSocket 연결 관리
├── recording_service.py     # 녹음 업로드/다운로드
├── stt_service.py           # STT 변환 로직
├── transcript_service.py    # 회의록 병합/관리
├── audio_preprocessor.py    # VAD 전처리
├── stt/
│   ├── base.py              # STTProvider 추상 클래스
│   ├── openai_provider.py   # OpenAI Whisper 구현
│   └── factory.py           # Provider 팩토리
└── sfu_service.py           # (미사용, 향후 SFU 전환용)
```

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
# 화자별 녹음을 타임스탬프 기반으로 병합
# 결과: 시간순 정렬된 Utterance 목록
utterances = [
    {"speaker_id": "user-1", "start_ms": 0, "text": "안녕하세요"},
    {"speaker_id": "user-2", "start_ms": 3800, "text": "네, 안녕하세요"},
]
```

### Environment Variables (STT)
```bash
OPENAI_API_KEY=sk-xxx           # OpenAI API 키
STT_PROVIDER=openai             # openai, local, self_hosted
ARQ_REDIS_URL=redis://redis:6379/1  # Worker용 별도 Redis DB
```
