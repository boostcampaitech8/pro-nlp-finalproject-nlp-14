# Active Context

## Current Progress

### Phase 1: 미팅 시스템 - 완료
- 인증 (JWT), 팀 CRUD, 회의 CRUD, 멤버/참여자 관리
- WebRTC Mesh P2P + 화면공유 (STUN only)
- 클라이언트 녹음 (MediaRecorder + IndexedDB + Presigned URL 업로드)
- 마이크 게인 조절, 오디오 디바이스 선택 UI

### Phase 2: PR Review 시스템 - 진행 중
- [x] 녹음 파일 STT 변환 (OpenAI Whisper API)
  - STT Provider 추상화 (OpenAI/Local/Self-hosted 확장 가능)
  - VAD (Voice Activity Detection)로 발화 구간만 추출
  - ARQ Worker로 비동기 처리
  - 화자별 발화 병합 (타임스탬프 기반)
- [x] 실시간 채팅 시스템 (WebSocket + DB 저장)
- [x] Host 강제 음소거 기능
- [x] Markdown 렌더링 지원
- [x] 참가자 다중 선택 추가
- [ ] 회의록 기본 기능 구현 (자동 생성, 조회, 수정)
- [ ] 회의록 Review UI (Comment, Suggestion)
- [ ] Ground Truth 관리

## Work Log

> 작업 완료 시 여기에 기록해주세요.

```
[2026-01-13] Transcribed Recording 다운로드 기능 추가
- Backend: recordings.py - get_meeting_recordings API에서 transcript 필드 반환 추가
  - transcript_text, transcript_language, transcription_started_at, transcription_completed_at, transcription_error
- Frontend: RecordingList.tsx 수정
  - 다운로드 버튼 조건 변경: completed -> completed || transcribed
  - Audio 버튼: 음성 파일 다운로드 (.webm)
  - Transcript 버튼: 개별 transcript 텍스트 다운로드 (.txt)

[2026-01-13] Frontend 코드 리팩토링
- RemoteAudio 컴포넌트 분리: MeetingRoom.tsx → RemoteAudio.tsx (~136줄 분리)
  - Web Audio API GainNode를 통한 볼륨 조절
  - setSinkId를 통한 출력 장치 선택
- localStorage 헬퍼 분리: meetingRoomStore.ts → utils/audioSettingsStorage.ts
  - loadAudioSettings, saveAudioSettings
  - loadRemoteVolumes, saveRemoteVolumes
- 리팩토링 분석 리포트 생성: reports/refactor/refactor_codebase_13-01-2026_180000.md

[2026-01-13] 수동 백업 시스템 추가
- make backup: PostgreSQL, MinIO, Redis 전체 백업
- make backup-list: 백업 목록 조회
- make backup-restore: 특정 백업에서 복원
- 백업 저장 위치: backup/YYYYMMDD_HHMMSS/ (.gitignore 추가)
- 프로덕션 자동 백업은 향후 별도 구현 예정

[2026-01-12] Phase 2-2: 실시간 기능 및 UI 개선
- 채팅 시스템: WebSocket 메시지 + DB 저장, ChatPanel 컴포넌트
- Host 강제 음소거: force-mute/force-muted 메시지, useForceMute 훅
- Markdown 렌더링: MarkdownRenderer 컴포넌트 (react-markdown)
- 참가자 다중 선택: ParticipantSection 체크박스 UI
- Docker 빌드 수정:
  - shared-types transcript 타입 export
  - RecordingStatus 7가지 값 추가
  - Dockerfile build-essential 추가 (webrtcvad gcc 빌드)
  - stt-worker: uv run 사용, setuptools 추가, redis_settings 수정
- MeetingRoom UI 개선:
  - 채팅 스크롤 수정 (h-screen, min-h-0, overflow-hidden)
  - 사이드바 접이식 UI (showParticipants, showChat 토글)
  - ChatPanel: hideHeader prop, isContinuousMessage 그룹화
- 사용자 설정 캐싱 (localStorage):
  - 마이크 게인, 오디오 디바이스 선택 캐싱
  - 참여자별 볼륨 설정 캐싱 (회의 간 유지)
  - meetingRoomStore에서 캐시 로드/저장 처리
- 채팅 히스토리 로드:
  - GET /meetings/{id}/chat API 추가
  - 회의 재입장 시 이전 채팅 메시지 로드
- Textarea 개선:
  - Shift+Enter 줄바꿈 지원 (chat, meeting/team description)
  - textarea 자동 높이 조절

[2026-01-10] Phase 2-1: 녹음 파일 STT 변환 구현 완료
- STT Provider 추상화: base.py, openai_provider.py, factory.py
- VAD 전처리: audio_preprocessor.py (webrtcvad 사용)
- 비즈니스 로직: stt_service.py, transcript_service.py
- ARQ Worker: arq_worker.py, run_worker.py (비동기 STT 처리)
- API 엔드포인트: transcripts.py (시작/상태/조회)
- DB 모델: MeetingTranscript, Recording 확장 (transcript 필드)
- Frontend: transcriptService.ts
- 환경변수: OPENAI_API_KEY, STT_PROVIDER, ARQ_REDIS_URL

[2026-01-08] API Contract 리팩토링 (Phase 1-3 완료)
- Phase 1 (HIGH): recording.yaml 참조 경로 수정, common types 사용, 페이지네이션 표준화
- Phase 2 (MEDIUM): team-member.yaml -> team.yaml, meeting-participant.yaml -> meeting.yaml 통합
- Phase 3 (LOW): TeamWithMembers, MeetingWithParticipants에 allOf 패턴 적용 (DRY)
- RecordingListResponse: recordings/total -> items/meta 변경 (Breaking Change)
- Backend/Frontend 동시 업데이트 완료

[2026-01-08] Frontend 리팩토링 및 테스트 수정
- useWebRTC 훅 분리 (useSignaling, usePeerConnections, useAudioDevices, useScreenShare, useRecording)
- useWebRTC.new.ts → useWebRTC.ts 파일명 변경
- 43개 테스트 모두 통과하도록 수정
- signalingClient mock getter 패턴 적용
- useEffect cleanup dependency array 수정 (unmount 시에만 실행)
- MeetingDetailPage, TeamDetailPage 컴포넌트 분리

[2026-01-08] 화면공유 수정
- 화면공유 버그 수정 (원격 참여자에게 화면공유 전달)

[2026-01-07] 회의 버그 수정
- 원격 오디오/화면공유 문제 수정

[2026-01-07] 녹음 안정성 개선
- Presigned URL 업로드, 토큰 자동 갱신, IndexedDB 증분 저장

[2026-01-06] 회의 UI 개선
- 마이크 게인 조절 기능 추가 (VolumeSlider)
- 오디오 디바이스 선택 UI (DeviceSelector)
- TURN 서버 제거, STUN only로 변경

[2026-01-06] Phase 1 완료
- WebRTC Mesh P2P, 클라이언트 녹음, 팀/회의 CRUD
```