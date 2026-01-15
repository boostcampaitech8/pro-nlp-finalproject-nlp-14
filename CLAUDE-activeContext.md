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
  - 클라이언트 VAD (@ricky0123/vad-web, Silero VAD) 우선 사용
  - 서버 VAD (webrtcvad) 폴백 지원
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
[2026-01-15] Spotlight 서비스 코드 리팩토링
- 목적: 코드 품질 개선, 버그 수정, DRY 원칙 적용
- Phase 1: LeftSidebar Timer Bug Fix
  - useState -> useRef 변경으로 re-render 시 duration 리셋 버그 수정
  - startTimeRef.current로 회의 시작 시간 추적
- Phase 2: Type Safety (useCommand.ts)
  - isValidPreviewType 타입 가드 함수 추가
  - 필드 키를 label -> id로 변경 (i18n 호환)
- Phase 3: Duplicate Data 제거
  - commandStore의 defaultSuggestions 제거
  - MainPage에서 agentService.getSuggestions()로 로드
- Phase 4: Constants & Utils 추출
  - src/app/constants/index.ts 생성 (HISTORY_LIMIT, STATUS_COLORS, API_DELAYS 등)
  - src/app/utils/dateUtils.ts 생성 (formatRelativeTime, formatDuration)
  - 6개 파일에서 하드코딩 값 -> 상수 참조로 변경
- Phase 5: Navigation 개선
  - SectionTitle 컴포넌트 추출 (반복 클래스 제거)
- Phase 6: MeetingModal Form State 통합
  - 5개 개별 useState -> 1개 formData 객체로 통합
  - updateField 헬퍼 함수로 필드 업데이트
- Phase 7: Placeholder 버튼 정리
  - PreviewHeader에서 미구현 ExternalLink, Maximize2 버튼 제거
- 수정된 파일: 10개 (2개 신규, 8개 수정)
- TypeScript 빌드: 에러 없음

[2026-01-15] Spotlight-style 메인 서비스 페이지 구현 (MIT-9)
- 목적: macOS Spotlight 스타일의 현대적인 메인 페이지 구현
- 구현 내용:
  - 3-column 레이아웃 (280px 좌측 사이드바, 중앙 컨텐츠, 400px 우측 사이드바)
  - Glassmorphism 디자인 시스템 (backdrop-blur, rgba 배경)
  - shadcn/ui 컴포넌트 통합 (Dialog, ScrollArea, Tooltip 등)
  - Spotlight 명령어 시스템 (자동완성, 히스토리)
  - framer-motion 애니메이션
- 새 파일 구조 (src/app/):
  - components/meeting/MeetingModal.tsx - 회의 생성 모달
  - components/sidebar/{LeftSidebar,Navigation,CurrentSession}.tsx - 사이드바
  - components/spotlight/SpotlightInput.tsx - 명령어 입력
  - components/ui/* - shadcn/ui 컴포넌트
  - hooks/useCommand.ts - 명령어 처리
  - layouts/MainLayout.tsx - 3-column 레이아웃
  - pages/MainPage.tsx - 메인 페이지
  - services/agentService.ts - 명령어 매칭/처리
  - stores/{commandStore,meetingModalStore,previewStore}.ts - 상태 관리
  - types/command.ts - 명령어 타입
- Zustand 스토어:
  - commandStore: 명령어 입력, 자동완성, 히스토리
  - meetingModalStore: 회의 모달 상태
  - previewStore: 미리보기 패널 상태
- 기존 페이지 마이그레이션:
  - HomePage, TeamDetailPage, MeetingDetailPage에 네비게이션 추가
  - CurrentSession에 회의 링크, 새 회의 버튼 추가
  - Navigation에 팀 목록, 회의 생성 버튼 추가
- 테스트/빌드 결과:
  - TypeScript: 에러 없음
  - ESLint: 소스 코드 에러 없음
  - Tests: 24 passed, 61 skipped
  - Build: 성공 (1.2MB JS bundle)
- 수정된 CSS:
  - index.css: hover:bg-white/8 -> hover:bg-white/5 (Tailwind 호환)

[2026-01-14] Frontend 테스트 인프라 개선 (진행 중)
- 목적: 테스트 환경 안정화 및 react-markdown 모킹
- test/setup.ts: jest-dom matcher 설정 방식 변경
  - @testing-library/jest-dom/vitest import에서 expect.extend(matchers) 방식으로 변경
- tsconfig.json: 테스트 파일 빌드 제외
  - exclude: ["**/*.test.ts", "**/*.test.tsx", "src/test", "vitest.config.ts"]
- vitest.config.ts: MarkdownRenderer mock alias 추가
  - @/components/ui/MarkdownRenderer -> ./src/test/mocks/MarkdownRenderer.tsx
- Mock 파일 생성:
  - src/__mocks__/react-markdown.tsx: react-markdown 라이브러리 mock (기본 Markdown 변환)
  - src/test/mocks/MarkdownRenderer.tsx: MarkdownRenderer 컴포넌트 mock
- 테스트 파일 수정:
  - ParticipantList.test.tsx: act() wrapper 추가 (비동기 렌더링 처리)
  - 기타 테스트 파일들 수정 중
- 현재 상태: 24 tests passed, 61 skipped (MarkdownRenderer.test.tsx 13개 skip 포함)
- 남은 작업: act() 경고 해결, skip된 테스트 재활성화

[2026-01-14] Transcript 실제 시각 표시 (MIT-7)
- Backend: transcript_service.py - Utterance에 absolute_timestamp 필드 추가
  - recording.started_at + segment.startMs로 wall-clock time 계산
  - 실제 시간 기준으로 발화 정렬 (대화 맥락 명확화)
  - meeting_start/meeting_end 계산 및 DB 저장
- Backend: models/transcript.py - meeting_start, meeting_end 컬럼 추가
- Backend: schemas/transcript.py - timestamp, meetingStart, meetingEnd 필드 추가
- Backend: endpoints/transcripts.py - timestamp 파싱 및 응답 포함
- DB Migration: a568e7cad9bd - meeting_start, meeting_end 컬럼 추가
- API Contract: transcript.yaml - Utterance에 timestamp (date-time) 필드 추가, MeetingTranscript에 meetingStart/meetingEnd 추가
- Frontend: TranscriptSection.tsx - formatTimestamp() 함수 추가, 발화 시간을 HH:MM:SS 형식으로 표시
- 효과: 여러 참여자의 발화가 실제 시간 순서대로 표시되어 회의 흐름 파악 용이

[2026-01-13] 클라이언트 VAD (Voice Activity Detection) 구현
- Frontend: @ricky0123/vad-web 패키지 추가 (Silero VAD, ONNX 기반)
- useVAD.ts: 실시간 발화 감지 훅 (onSpeechStart/onSpeechEnd 콜백)
- useRecording.ts: VAD 통합, enableVAD 옵션, isSpeaking 상태
- recordingService.ts: VAD 메타데이터 업로드 지원
- Backend: vad_segments JSONB 컬럼 추가 (MeetingRecording 모델)
- recording.py (schema): VADSegment, VADMetadata, VADSettings 스키마
- stt_service.py: 클라이언트 VAD 우선 사용, 서버 VAD 폴백
- audio_preprocessor.py: extract_segment() 메서드 추가
- DB 마이그레이션: 56401abb2fd4_add_vad_segments_to_meeting_recordings.py
- 효과: 서버 VAD 분석 부하 제거, 클라이언트에서 실시간 발화 상태 표시 가능

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