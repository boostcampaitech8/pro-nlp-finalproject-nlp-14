# Active Context

## Current Progress

### Phase 1: 미팅 시스템 - 완료
- 인증 (JWT), 팀 CRUD, 회의 CRUD, 멤버/참여자 관리
- LiveKit SFU 미디어 라우팅 (Mesh P2P -> SFU 마이그레이션 완료)
- 서버 녹음 (LiveKit Egress -> MinIO)
- 클라이언트 VAD -> DataPacket으로 발화 이벤트 전송
- 마이크 게인 조절, 오디오 디바이스 선택 UI
- 화면공유, Host 강제 음소거, 채팅 (DataPacket 기반)

### Phase 2: PR Review 시스템 - 진행 중
- [x] 녹음 파일 STT 변환 (OpenAI Whisper API)
  - STT Provider 추상화 (OpenAI/Local/Self-hosted 확장 가능)
  - 클라이언트 VAD (@ricky0123/vad-web, Silero VAD) 우선 사용
  - 서버 VAD (webrtcvad) 폴백 지원
  - ARQ Worker로 비동기 처리
  - 화자별 발화 병합 (타임스탬프 기반)
- [x] 실시간 채팅 시스템 (DataPacket + DB 저장)
- [x] Host 강제 음소거 기능
- [x] Markdown 렌더링 지원
- [x] 참가자 다중 선택 추가
- [x] 서버 녹음 (LiveKit Egress Composite) UI 지원
- [ ] 회의록 기본 기능 구현 (자동 생성, 조회, 수정)
- [ ] 회의록 Review UI (Comment, Suggestion)
- [ ] Ground Truth 관리

## Work Log

> 최근 작업 기록 (이전 기록: CLAUDE-archived-worklog.md)

```
[2026-01-21] Conversation System 리팩토링 (MIT-9)
- 리팩토링 분석 보고서 기반 작업 수행
- Phase 1: 유틸리티 함수 추출
  - previewUtils.ts: 프리뷰 검증 및 업데이트 로직 (~30 lines 중복 제거)
  - historyUtils.ts: 히스토리 아이템 생성 로직 (~30 lines 중복 제거)
- Phase 2: Mock 데이터 분리
  - mockResponses.ts: Mock 응답 데이터 정의 분리
  - commandMatcher.ts: Strategy Pattern으로 명령어 매칭 (cyclomatic complexity 12 -> ~3)
  - agentService.ts: 384 lines -> ~146 lines 감소
- 테스트: Docker 배포 환경(mit-hub.com)에서 baseline + post-refactoring 검증 완료

[2026-01-21] Spotlight Chat-like Conversation System 구현 (MIT-9)
- 기능: 명령 실행 시 입력창이 하단으로 이동, 대화 버블로 상호작용
- 레이아웃 모드: center-only, fullscreen, center-right-merged (기본값: fullscreen)
- 컴포넌트: ConversationContainer, ChatMessageList, UserMessageBubble, AgentMessageBubble 등
- 스토어: conversationStore (isConversationActive, messages, pendingForm, layoutMode)
- 버그 수정: React closure 문제로 agent message 로딩 상태 고착
  - 원인: Zustand 훅에서 destructure한 값이 async 콜백 생성 시점에 캡처됨
  - 수정: useConversationStore.getState()로 최신 상태 직접 조회
- 채팅 버블 마크다운 렌더링: AgentMessageBubble에서 previewData.content를 마크다운으로 표시
  - MarkdownRenderer 컴포넌트 재사용
  - 어두운 배경용 스타일: .chat-bubble-markdown (index.css)

[2026-01-20] LiveKit 웹훅 서명 검증 및 녹음 생성 버그 수정
- 문제: 회의 종료 후 녹음 레코드가 DB에 생성되지 않음
- 원인 1: MessageToDict(preserving_proto_field_name=True)가 snake_case 출력
  - 코드는 egressInfo, roomName (camelCase) 기대
  - 실제: egress_info, room_name (snake_case) 수신
- 원인 2: Python logging 미설정으로 디버그 로그 미출력
- 수정:
  - livekit_webhooks.py: MessageToDict에 preserving_proto_field_name=False 설정
  - main.py: logging.basicConfig() 추가
  - 웹훅 서명 검증: TokenVerifier + WebhookReceiver 패턴 구현
- 추가: Redis 기반 egress 상태 관리, 녹음 시작 알림 UI

[2026-01-20] LiveKit Egress 녹음 상태 동기화 버그 수정
- 증상: 녹음 시작/중지 시 400 Bad Request
- 원인: _active_egress 메모리 캐시가 실제 LiveKit 상태와 동기화 안됨
- 수정:
  - livekit_service.py: start_room_recording()에서 LiveKit API로 실제 상태 확인
  - livekit_service.py: clear_active_egress() 메서드 추가
  - livekit_webhooks.py: 모든 종료 상태(COMPLETE/FAILED/ABORTED)에서 캐시 정리

[2026-01-20] LiveKit TURN/WebRTC 연결 디버깅
- ICE candidate pair 실패 원인 분석: UDP 포트 미개방
- 필수 포트포워딩 목록 정리:
  - 5349/TCP (TURN TLS) - 열림
  - 3478/UDP (TURN UDP)
  - 50000-50100/UDP (WebRTC RTC)
  - 30000-30050/UDP (TURN relay)
- nginx stream 블록: 5349 직접 노출 시 불필요 (443 공유 시에만 필요)

[2026-01-19] Memory Bank 최적화
- CLAUDE-activeContext.md 86% 축소 (16KB -> 2KB)
- CLAUDE-patterns.md에서 REMOVED/DEPRECATED 섹션 제거
- CLAUDE-decisions.md에서 deprecated decisions (D1-D3, D10) 제거
- backend/CLAUDE-*.md 파일 현재 상태로 업데이트

[2026-01-19] LiveKit Egress Composite 녹음 수정
- RecordingResponse 스키마 user_id nullable 처리 (composite 녹음 지원)
- RecordingList.tsx: "Server Recording" 표시 (user_id가 null인 경우)
- api-contract 동기화 완료

[2026-01-18] LiveKit TURN TLS 활성화 설정
- Let's Encrypt 인증서 마운트 (전체 /etc/letsencrypt 마운트로 심볼릭 링크 유지)
- docker-compose.yml LIVEKIT_CONFIG에 cert_file, key_file 경로 추가

[2026-01-16] LiveKit SDK 타입 오류 수정
- rtcConfig를 Room constructor -> room.connect()로 이동 (SDK 2.17.0 타입 호환)

[2026-01-16] LiveKit Egress 및 WebSocket 프록시 수정
- EGRESS_CONFIG_BODY 인라인 설정으로 변경
- nginx /livekit/ WebSocket 프록시 추가

[2026-01-15] WebRTC Mesh P2P -> LiveKit SFU 마이그레이션 완료 (MIT-14)
- useLiveKit.ts 신규 생성 (서버 녹음, DataPacket 채팅/VAD)
- 레거시 코드 삭제 (useWebRTC, useSignaling, usePeerConnections)

[2026-01-15] Spotlight 서비스 구현 (MIT-9)
- 3-column 레이아웃, Glassmorphism 디자인
- 명령어 시스템 (commandStore, agentService)
```