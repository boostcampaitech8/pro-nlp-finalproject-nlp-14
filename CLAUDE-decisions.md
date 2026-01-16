# Architecture Decisions

## WebRTC / LiveKit

### D1: Mesh P2P (STUN only) - DEPRECATED
- **결정**: TURN 서버 없이 STUN만 사용
- **근거**:
  - 프로토타입 단계에서 비용 절감
  - 같은 네트워크/NAT 호환 환경에서 충분히 동작
- **제한**: Symmetric NAT 환경에서 연결 실패 가능
- **상태**: D26 LiveKit SFU로 대체됨

### D2: 클라이언트 측 녹음 - DEPRECATED
- **결정**: MediaRecorder API로 클라이언트에서 녹음
- **근거**:
  - SFU 없이 구현 가능
  - 서버 부하 최소화
  - 각 참여자별 개별 녹음 가능
- **구현**: IndexedDB 증분 저장 + Presigned URL 업로드
- **상태**: D26 서버 녹음(LiveKit Egress)으로 대체됨

### D3: 화면공유 별도 피어 연결 - DEPRECATED
- **결정**: 화면공유용 RTCPeerConnection 분리
- **근거**:
  - 오디오와 화면 트랙 독립적 관리
  - 화면공유 시작/중지가 오디오에 영향 없음
- **상태**: D26 LiveKit 통합 트랙 관리로 대체됨

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

## Storage

### D4: Presigned URL 업로드
- **결정**: 녹음 파일은 MinIO에 직접 업로드
- **근거**:
  - nginx 파일 크기 제한 우회
  - 서버 메모리 부하 감소
- **흐름**:
  1. Backend에서 presigned URL 발급
  2. Frontend가 MinIO에 직접 PUT
  3. Backend에서 업로드 확인

### D5: IndexedDB 증분 저장
- **결정**: 녹음 청크를 10초마다 IndexedDB에 저장
- **근거**:
  - 브라우저 크래시/새로고침 시 데이터 손실 방지
  - 메모리 사용량 관리
- **구현**: recordingStorageService로 청크 관리

## Authentication

### D6: JWT + 자동 갱신
- **결정**: 30분 access token + 7일 refresh token
- **근거**: 보안과 UX 균형
- **구현**:
  - 회의 중 15분마다 자동 갱신 (ensureValidToken)
  - auth:logout 이벤트로 전역 로그아웃 처리

## State Management

### D7: Zustand 개별 Selector
- **결정**: 스토어 전체 대신 개별 상태 selector 사용
- **근거**: useCallback 의존성으로 인한 무한 루프 방지
- **패턴**:
  ```typescript
  // 상태
  const connectionState = useMeetingRoomStore((s) => s.connectionState);
  // 액션
  const setConnectionState = useMeetingRoomStore((s) => s.setConnectionState);
  ```

## API Design

### D8: API Contract First
- **결정**: OpenAPI 명세를 Single Source of Truth로 사용
- **근거**: FE/BE 타입 일관성 보장
- **워크플로우**:
  1. api-contract/openapi.yaml 수정
  2. pnpm run generate:types
  3. Backend 구현
  4. Frontend 구현

### D9: UUID 사용
- **결정**: 모든 엔티티에 UUID 사용 (auto-increment 금지)
- **근거**:
  - 분산 시스템 확장성
  - ID 추측 공격 방지

### D12: 페이지네이션 표준화
- **결정**: 모든 목록 API는 `items` + `meta` 형식 사용
- **근거**: 일관된 응답 포맷으로 프론트엔드 코드 재사용성 향상
- **패턴**:
  ```yaml
  ListResponse:
    properties:
      items: [...]
      meta:
        $ref: './common.yaml#/components/schemas/PaginationMeta'
  ```

### D13: OpenAPI allOf 합성
- **결정**: 확장 스키마에 allOf 패턴 사용 (TeamWithMembers, MeetingWithParticipants)
- **근거**:
  - DRY 원칙 준수 (중복 속성 제거)
  - 기본 스키마 변경 시 자동 반영
- **패턴**:
  ```yaml
  TeamWithMembers:
    allOf:
      - $ref: '#/components/schemas/Team'
      - type: object
        properties:
          members: [...]
  ```

### D14: 스키마 파일 통합
- **결정**: 작은 스키마 파일을 도메인 파일에 통합
- **근거**:
  - 파일 수 감소 (9 -> 7)
  - 관련 스키마 응집도 향상
- **적용**:
  - team-member.yaml -> team.yaml
  - meeting-participant.yaml -> meeting.yaml

## Frontend Architecture

### D10: useWebRTC 훅 분리
- **결정**: useWebRTC를 기능별 하위 훅으로 분리
- **근거**:
  - 단일 책임 원칙 (SRP) 준수
  - 테스트 용이성 향상
  - 코드 가독성 및 유지보수성 개선
- **구조**:
  ```
  useWebRTC (통합)
  ├── useSignaling        # 시그널링 연결/메시지
  ├── usePeerConnections  # P2P 연결 관리
  ├── useAudioDevices     # 오디오 디바이스
  ├── useScreenShare      # 화면공유
  └── useRecording        # 녹음
  ```

### D11: 페이지 컴포넌트 분리
- **결정**: 대형 페이지 컴포넌트를 기능별 섹션 컴포넌트로 분리
- **근거**:
  - 파일 크기 감소 및 가독성 향상
  - 컴포넌트 재사용 가능
- **적용**:
  - MeetingDetailPage → MeetingInfoCard, ParticipantSection, RecordingList
  - TeamDetailPage → TeamInfoCard, TeamMemberSection, MeetingListSection

### D15: LocalStorage 사용자 설정 캐싱
- **결정**: 회의실 오디오 설정을 localStorage에 캐싱
- **근거**:
  - 사용자가 다른 회의에서도 선호 설정 유지 기대
  - 참여자별 볼륨 설정은 다른 회의에서도 동일 참여자에게 적용
- **저장 항목**:
  - `mit-audio-settings`: micGain, audioInputDeviceId, audioOutputDeviceId
  - `mit-remote-volumes`: userId별 볼륨 (Map -> Object 변환)
- **구현 위치**: `meetingRoomStore.ts`의 setter 함수들
- **주의**: 스토어 reset() 시에도 캐시 설정은 유지

## STT & Transcript

### D16: Transcript 실제 시각 저장
- **결정**: 발화 시각을 녹음 상대 시간이 아닌 wall-clock timestamp로 저장
- **근거**:
  - 여러 참여자의 녹음을 병합할 때 실제 대화 순서 보장
  - 각 녹음의 `started_at`이 다르므로 상대 시간(`startMs`)만으로는 순서 불명확
  - UI에서 실제 발화 시각 표시 가능 (예: "15:30:45")
- **구현**:
  - Backend: `absolute_timestamp = recording.started_at + timedelta(milliseconds=startMs)`
  - DB: `timestamp` 필드에 ISO 8601 형식으로 저장
  - API: `Utterance` 스키마에 `timestamp` (date-time) 필드 추가
  - Frontend: `formatTimestamp(utterance.timestamp)` -> "HH:MM:SS"
- **정렬**: `absolute_timestamp` 기준으로 발화 정렬 (시간 순서 보장)
- **메타데이터**: `meeting_start`, `meeting_end` 필드 추가 (회의 실제 시작/종료 시각)

## UI Architecture

### D17: Spotlight-style 메인 서비스 페이지
- **결정**: macOS Spotlight 스타일의 3-column 레이아웃 메인 페이지 구현
- **근거**:
  - 현대적인 UX 제공 (Raycast, Alfred 스타일)
  - 자연어 명령어 입력으로 빠른 작업 수행
  - 컨텍스트 미리보기로 정보 탐색 효율성 향상
- **구조**:
  - 좌측 (280px): 네비게이션, 팀 목록, 현재 세션
  - 중앙: Spotlight 입력, 명령 결과
  - 우측 (400px): 선택 항목 미리보기
- **위치**: `frontend/src/app/`

### D18: Glassmorphism 디자인 시스템
- **결정**: 반투명 글래스 효과 기반 UI 디자인
- **근거**:
  - 시각적 깊이감 제공 (레이어 구분)
  - 모던한 미적 감각
  - 다크 테마와 잘 어울림
- **구현**:
  - `backdrop-filter: blur()` 사용
  - `rgba()` 배경색으로 투명도 조절
  - 커스텀 Tailwind 색상 (`glass`, `card-bg`, `mit-primary`)
- **주의**: 성능 고려 - 중첩 blur 최소화

### D19: Modal Store 분리 패턴
- **결정**: 모달 상태를 별도 Zustand 스토어로 관리
- **근거**:
  - 모달 트리거와 상태 분리 (여러 위치에서 열기 가능)
  - 초기 데이터 전달 용이
  - 컴포넌트 간 결합도 감소
- **패턴**:
  ```typescript
  // 명령어에서 열기
  openModal({ title: '새 회의', teamId });
  // 버튼에서 열기
  <button onClick={() => openModal()}>새 회의</button>
  // 네비게이션에서 열기
  openModal({ teamId: currentTeam.id });
  ```
- **적용**: `meetingModalStore.ts`

### D20: Command System 아키텍처
- **결정**: 패턴 매칭 기반 명령어 시스템
- **근거**:
  - 자연어 입력 지원 (한글/영어)
  - 확장 가능한 명령어 추가
  - 자동완성 및 히스토리 지원
- **구조**:
  - `agentService.ts`: 명령어 패턴 정의 및 매칭
  - `commandStore.ts`: 입력/자동완성/히스토리 상태
  - `useCommand.ts`: 명령어 실행 및 응답 처리
- **응답 타입**:
  - `direct`: 직접 결과 표시
  - `navigation`: 페이지 이동
  - `modal`: 모달 열기
  - `form`: 폼 입력 필요

## Code Quality

### D21: Constants 중앙 관리
- **결정**: 매직 넘버와 반복 설정값을 `constants/index.ts`에서 관리
- **근거**:
  - DRY 원칙 (값 변경 시 한 곳만 수정)
  - 코드 가독성 향상 (의미 있는 상수명)
  - 일관성 유지 (여러 파일에서 동일 값 사용)
- **적용 항목**:
  - `HISTORY_LIMIT`, `SUGGESTIONS_DISPLAY_LIMIT` (UI 제한)
  - `STATUS_COLORS` (상태별 Tailwind 클래스)
  - `PREVIEW_TITLES` (타입별 제목)
  - `API_DELAYS` (Mock API 딜레이)

### D22: Type Guard 우선 사용
- **결정**: `as` type assertion 대신 type guard 함수 사용
- **근거**:
  - 런타임 타입 검증으로 안전성 향상
  - 예상치 못한 타입에 대한 폴백 처리 가능
  - 컴파일 타임과 런타임 타입 일치 보장
- **패턴**:
  ```typescript
  function isValidPreviewType(type: string): type is PreviewType {
    return VALID_TYPES.includes(type as PreviewType);
  }
  ```

### D23: Form State 통합
- **결정**: 관련된 폼 필드를 단일 객체로 통합
- **근거**:
  - 여러 useState가 각각 re-render 유발하는 문제 해결
  - 폼 초기화/리셋 로직 단순화
  - 관련 상태의 응집도 향상
- **패턴**: FormData 인터페이스 + updateField 헬퍼

### D24: useRef for Non-UI State
- **결정**: UI 렌더링에 영향 없는 값은 useState 대신 useRef 사용
- **근거**:
  - re-render에도 값 유지 (타이머 시작 시간 등)
  - 불필요한 re-render 방지
  - useEffect 의존성 배열 간소화
- **주의**: UI에 반영해야 하는 값은 여전히 useState 사용

### D25: Suggestions SSOT (Single Source of Truth)
- **결정**: suggestions 데이터를 agentService에서만 관리
- **근거**:
  - commandStore의 defaultSuggestions 중복 제거
  - API 연동 시 자연스러운 전환
  - 데이터 일관성 보장
- **구현**: MainPage useEffect에서 agentService.getSuggestions() 호출
