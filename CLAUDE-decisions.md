# Architecture Decisions

## WebRTC

### D1: Mesh P2P (STUN only)
- **결정**: TURN 서버 없이 STUN만 사용
- **근거**:
  - 프로토타입 단계에서 비용 절감
  - 같은 네트워크/NAT 호환 환경에서 충분히 동작
- **제한**: Symmetric NAT 환경에서 연결 실패 가능
- **향후**: 사용자 증가 시 TURN 서버 추가 또는 SFU 전환 고려

### D2: 클라이언트 측 녹음
- **결정**: MediaRecorder API로 클라이언트에서 녹음
- **근거**:
  - SFU 없이 구현 가능
  - 서버 부하 최소화
  - 각 참여자별 개별 녹음 가능
- **구현**: IndexedDB 증분 저장 + Presigned URL 업로드

### D3: 화면공유 별도 피어 연결
- **결정**: 화면공유용 RTCPeerConnection 분리
- **근거**:
  - 오디오와 화면 트랙 독립적 관리
  - 화면공유 시작/중지가 오디오에 영향 없음

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
