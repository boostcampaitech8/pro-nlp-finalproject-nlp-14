# Frontend Refactoring Analysis Report

**Generated:** 2026-01-08 14:15:00
**Target:** `frontend/` (37 files, 6,878 lines)
**Mode:** Analysis Only (No Code Modifications)

---

## Executive Summary

Frontend 코드베이스 전체에 대한 리팩토링 분석을 수행했습니다. 총 37개 파일, 6,878 라인의 코드를 분석한 결과, **테스트가 전혀 없고**, 일부 파일에서 **과도한 복잡도**가 발견되었습니다. 특히 `useWebRTC.ts`는 1,109 라인으로 가장 큰 파일이며, 다양한 책임이 혼재되어 있어 분리가 필요합니다.

### Risk Level: HIGH

- 테스트 커버리지: **0%** (테스트 파일 없음)
- 고복잡도 파일: **5개** (300+ 라인)
- 기술 부채: **높음** (God Object 패턴, SRP 위반)

---

## 1. Project Structure Analysis

### 1.1 File Distribution

| Category | Files | Lines | Percentage |
|----------|-------|-------|------------|
| Hooks | 4 | 1,445 | 21.0% |
| Pages | 6 | 1,447 | 21.0% |
| Components | 12 | 1,396 | 20.3% |
| Services | 8 | 1,283 | 18.7% |
| Stores | 3 | 816 | 11.9% |
| Types | 2 | 329 | 4.8% |
| Other | 2 | 162 | 2.3% |

### 1.2 File Size Distribution

| Size Range | Files | Files |
|------------|-------|-------|
| 500+ lines | 3 | useWebRTC.ts, MeetingDetailPage.tsx, TeamDetailPage.tsx |
| 300-499 lines | 3 | recordingStorageService.ts, MeetingRoom.tsx, teamStore.ts |
| 200-299 lines | 5 | meetingRoomStore.ts, webrtc.ts, webrtcService.ts, useAudioLevel.ts, AudioControls.tsx |
| 100-199 lines | 12 | api.ts, ParticipantList.tsx, HomePage.tsx, etc. |
| < 100 lines | 14 | 기타 파일들 |

---

## 2. Test Coverage Analysis

### 2.1 Current State

```
Test Files Found: 0
Test Coverage: 0%
Testing Framework: None configured
```

### 2.2 Missing Test Infrastructure

- `jest.config.js` / `vitest.config.ts` 없음
- `@testing-library/react` 미설치
- `jest` / `vitest` 미설치
- `__tests__` 또는 `*.test.ts(x)` 파일 없음

### 2.3 Recommended Test Priority

| Priority | Component | Reason |
|----------|-----------|--------|
| P0 (Critical) | useWebRTC.ts | 핵심 비즈니스 로직, 복잡도 높음 |
| P0 (Critical) | recordingStorageService.ts | 데이터 손실 위험, IndexedDB 의존 |
| P1 (High) | teamStore.ts | 상태 관리 로직 |
| P1 (High) | meetingRoomStore.ts | 실시간 상태 관리 |
| P2 (Medium) | api.ts | 인증 및 토큰 갱신 로직 |
| P2 (Medium) | signalingService.ts | WebSocket 통신 |

---

## 3. Complexity Analysis

### 3.1 Critical Files (Cyclomatic Complexity)

#### 3.1.1 useWebRTC.ts (1,109 lines) - CRITICAL

**Complexity Metrics:**
- Zustand Selectors: 33개 (lines 22-65)
- useRef Declarations: 12개 (lines 67-85)
- useState Declarations: 4개 (lines 75-78)
- useCallback Functions: 15+개
- useEffect Hooks: 6개 (lines 958, 965, 978, 1009, 1017, 1042)
- Switch Cases in handleSignalingMessage: 15개

**Identified Issues:**
1. **God Object Anti-pattern**: 하나의 훅에 시그널링, 피어 연결, 녹음, 화면공유, 오디오 장치 관리 모두 포함
2. **SRP Violation**: 단일 책임 원칙 위반 - 최소 5개 이상의 관심사 혼재
3. **Excessive Dependencies**: 33개 selector가 각각 의존성 배열에 포함
4. **Complex State Machine**: 명시적 상태 머신 없이 암시적 상태 전이
5. **Deep Callback Nesting**: useCallback 내부에서 다른 useCallback 참조

**Function Complexity:**

| Function | Lines | Complexity | Issue |
|----------|-------|------------|-------|
| handleSignalingMessage | 153 | Very High | 15 case 분기, 중첩 로직 |
| stopRecordingInternal | 120 | High | Promise 내 복잡한 로직 |
| startScreenShare | 77 | High | 피어 연결 + 시그널링 혼합 |
| joinRoom | 38 | Medium | 여러 단계 초기화 |
| createPeerConnectionForUser | 47 | Medium | 콜백 중첩 |

#### 3.1.2 MeetingDetailPage.tsx (599 lines)

**Complexity Metrics:**
- useState Declarations: 16개
- Event Handlers: 8개
- useEffect Hooks: 2개
- Conditional Renders: 10+개

**Identified Issues:**
1. **Large Component**: UI + 비즈니스 로직이 한 파일에 혼재
2. **State Bloat**: 16개 useState는 Custom Hook 또는 Reducer로 분리 필요
3. **Inline Event Handlers**: 일부 핸들러가 JSX 내에 인라인으로 정의

#### 3.1.3 TeamDetailPage.tsx (505 lines)

MeetingDetailPage와 유사한 패턴의 문제:
- useState: 14개
- Event Handlers: 7개
- 중복 코드: STATUS_LABELS, STATUS_COLORS, ROLE_LABELS 등이 여러 파일에 중복

#### 3.1.4 recordingStorageService.ts (420 lines)

**Complexity Metrics:**
- Public Methods: 11개
- IndexedDB Transactions: 10개
- Error Handling Blocks: 15개

**Identified Issues:**
1. **Manual Promise Wrapping**: IndexedDB API를 수동으로 Promise로 래핑
2. **Repetitive Transaction Pattern**: 각 메서드에서 트랜잭션 패턴 반복
3. **No Retry Logic**: 실패 시 재시도 로직 없음

#### 3.1.5 MeetingRoom.tsx (384 lines)

**Identified Issues:**
1. **Inline Component**: RemoteAudio 컴포넌트가 파일 내에 인라인 정의 (160 lines)
2. **Complex Audio Setup**: Web Audio API 설정 로직이 컴포넌트에 포함
3. **Props Drilling**: 많은 props가 useWebRTC에서 하위 컴포넌트로 전달

### 3.2 Store Complexity

#### meetingRoomStore.ts (320 lines)

**State Fields:** 17개
**Actions:** 25개

| Category | Fields | Actions |
|----------|--------|---------|
| Meeting Info | 4 | 1 |
| Connection | 2 | 2 |
| Participants | 1 | 4 |
| Local Media | 4 | 4 |
| Remote Media | 3 | 4 |
| Peer Connections | 1 | 3 |
| Screen Sharing | 4 | 7 |

**Issue:** 단일 스토어에 너무 많은 상태와 액션이 집중됨

#### teamStore.ts (374 lines)

**State Fields:** 8개
**Actions:** 16개

비교적 잘 구조화되어 있으나, 팀과 회의 관련 로직이 혼재

---

## 4. Code Patterns Analysis

### 4.1 Good Patterns (Keep)

1. **Individual Zustand Selectors** (CLAUDE-patterns.md 준수)
   ```typescript
   // Good - 무한 루프 방지
   const connectionState = useMeetingRoomStore((s) => s.connectionState);
   ```

2. **Service Layer Separation**
   - webrtcService, signalingService, recordingService 등 분리

3. **Presigned URL Upload Pattern**
   - 대용량 파일 직접 업로드로 서버 부하 감소

### 4.2 Anti-patterns (Fix)

1. **God Hook** - useWebRTC
   ```typescript
   // Problem: 1,109 lines, 5+ concerns
   export function useWebRTC(meetingId: string) {
     // signaling, peer connections, recording, screen share, audio devices...
   }
   ```

2. **Component State Bloat**
   ```typescript
   // Problem: 16 useState in MeetingDetailPage
   const [isEditing, setIsEditing] = useState(false);
   const [editTitle, setEditTitle] = useState('');
   // ... 14 more
   ```

3. **Duplicate Constants**
   ```typescript
   // Problem: STATUS_LABELS, ROLE_LABELS duplicated across files
   // TeamDetailPage.tsx, MeetingDetailPage.tsx
   const STATUS_LABELS: Record<MeetingStatus, string> = {...};
   ```

4. **Inline Child Components**
   ```typescript
   // Problem: RemoteAudio defined inside MeetingRoom.tsx
   function RemoteAudio({...}) { /* 160 lines */ }
   export function MeetingRoom() { /* uses RemoteAudio */ }
   ```

### 4.3 Missing Patterns

1. **Error Boundaries**: React Error Boundary 없음
2. **Loading States**: Suspense 미사용
3. **Memoization**: useMemo 활용 부족 (일부 컴포넌트)
4. **Type Guards**: 런타임 타입 검증 없음

---

## 5. Refactoring Strategy

### 5.1 Priority Matrix

| Priority | Task | Risk | Effort | Impact |
|----------|------|------|--------|--------|
| P0 | useWebRTC 분리 | High | High | Critical |
| P0 | 테스트 인프라 구축 | Low | Medium | Critical |
| P1 | Page 컴포넌트 분리 | Medium | Medium | High |
| P1 | 상수 중앙화 | Low | Low | Medium |
| P2 | Store 분리 | Medium | Medium | Medium |
| P2 | RemoteAudio 분리 | Low | Low | Medium |
| P3 | Error Boundary 추가 | Low | Low | Low |

### 5.2 Detailed Refactoring Plans

#### 5.2.1 useWebRTC.ts Decomposition (P0)

**Current Structure:**
```
useWebRTC (1,109 lines)
├── Signaling Logic (~300 lines)
├── Peer Connection Management (~250 lines)
├── Recording Logic (~350 lines)
├── Screen Sharing (~100 lines)
└── Audio Device Management (~100 lines)
```

**Target Structure:**
```
hooks/
├── useWebRTC.ts (~150 lines) - Orchestrator
├── useSignaling.ts (~200 lines)
├── usePeerConnections.ts (~200 lines)
├── useRecording.ts (~300 lines)
├── useScreenShare.ts (~100 lines)
└── useAudioDevices.ts (~100 lines) - Already exists, expand
```

**Migration Steps:**
1. Extract `useSignaling` hook
   - handleSignalingMessage
   - signalingClient interactions

2. Extract `usePeerConnections` hook
   - createPeerConnectionForUser
   - createScreenPeerConnectionForUser
   - Peer connection state management

3. Extract `useRecording` hook
   - startRecordingInternal
   - stopRecordingInternal
   - saveChunksToStorage
   - uploadPendingRecordings
   - IndexedDB interactions

4. Expand existing `useAudioDevices` hook
   - changeAudioInputDevice
   - changeAudioOutputDevice
   - changeMicGain

5. Keep `useWebRTC` as orchestrator
   - Compose all sub-hooks
   - Manage lifecycle (joinRoom, leaveRoom)
   - Export unified API

**Risk Mitigation:**
- Create integration tests BEFORE refactoring
- Refactor incrementally, one extraction at a time
- Maintain backward-compatible API during migration

#### 5.2.2 Test Infrastructure Setup (P0)

**Recommended Stack:**
```json
{
  "devDependencies": {
    "vitest": "^1.0.0",
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/user-event": "^14.0.0",
    "jsdom": "^23.0.0",
    "msw": "^2.0.0"
  }
}
```

**Initial Test Files:**
```
frontend/
├── src/
│   ├── hooks/
│   │   └── __tests__/
│   │       ├── useWebRTC.test.ts
│   │       ├── useAuth.test.ts
│   │       └── useAudioDevices.test.ts
│   ├── services/
│   │   └── __tests__/
│   │       ├── recordingStorageService.test.ts
│   │       └── api.test.ts
│   └── stores/
│       └── __tests__/
│           ├── teamStore.test.ts
│           └── meetingRoomStore.test.ts
└── vitest.config.ts
```

#### 5.2.3 Page Component Decomposition (P1)

**MeetingDetailPage.tsx Target Structure:**
```
pages/MeetingDetailPage.tsx (~150 lines)
├── components/
│   ├── MeetingDetailHeader.tsx
│   ├── MeetingEditForm.tsx
│   ├── MeetingInfo.tsx
│   ├── MeetingParticipants.tsx
│   └── MeetingRecordings.tsx
└── hooks/
    └── useMeetingDetail.ts (custom hook for state/logic)
```

**TeamDetailPage.tsx Target Structure:**
```
pages/TeamDetailPage.tsx (~150 lines)
├── components/
│   ├── TeamHeader.tsx
│   ├── MeetingList.tsx
│   ├── CreateMeetingForm.tsx
│   └── TeamMembers.tsx
└── hooks/
    └── useTeamDetail.ts
```

#### 5.2.4 Constants Centralization (P1)

**Create shared constants file:**
```typescript
// src/constants/meeting.ts
export const STATUS_LABELS: Record<MeetingStatus, string> = {
  scheduled: 'Scheduled',
  ongoing: 'Ongoing',
  completed: 'Completed',
  in_review: 'In Review',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
};

export const STATUS_COLORS: Record<MeetingStatus, string> = {...};

// src/constants/team.ts
export const ROLE_LABELS: Record<TeamRole, string> = {...};
export const ROLE_COLORS: Record<TeamRole, string> = {...};
```

#### 5.2.5 Store Separation (P2)

**meetingRoomStore.ts Split:**
```
stores/
├── meeting/
│   ├── meetingInfoStore.ts (meeting info, ICE servers)
│   ├── participantsStore.ts (participants, mute states)
│   ├── mediaStore.ts (local/remote streams, volumes)
│   ├── connectionStore.ts (peer connections)
│   └── screenShareStore.ts (screen sharing state)
└── meetingRoomStore.ts (facade that composes above)
```

---

## 6. Risk Assessment

### 6.1 High Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| useWebRTC 리팩토링 중 기존 기능 손상 | Critical | High | 테스트 먼저 작성, 점진적 마이그레이션 |
| 실시간 통신 로직 분리 시 타이밍 이슈 | High | Medium | useEffect 의존성 주의 깊게 관리 |
| IndexedDB 로직 변경 시 데이터 손실 | Critical | Low | 마이그레이션 스크립트 + 백업 |

### 6.2 Medium Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Store 분리 시 상태 동기화 문제 | Medium | Medium | Zustand middleware로 상태 관리 |
| 컴포넌트 분리 후 props drilling 증가 | Medium | High | Context 또는 Zustand 활용 |
| 타입 정의 중복/불일치 | Low | Medium | 공유 types 폴더 정리 |

### 6.3 Dependency Risks

**External Dependencies (Outdated Check Needed):**
```
react: 18.3.1
zustand: 5.0.2
axios: 1.7.9
react-router-dom: 7.1.1
```

**Browser API Dependencies:**
- MediaRecorder API (Chrome/Firefox 지원)
- IndexedDB (모든 브라우저)
- Web Audio API (모든 브라우저)
- setSinkId (Chrome 전용)

---

## 7. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
1. [ ] Vitest 설정 및 테스트 인프라 구축
2. [ ] useWebRTC 통합 테스트 작성
3. [ ] recordingStorageService 단위 테스트 작성
4. [ ] 상수 파일 중앙화

### Phase 2: Core Refactoring (Week 3-4)
1. [ ] useSignaling 추출
2. [ ] usePeerConnections 추출
3. [ ] useRecording 추출
4. [ ] useWebRTC를 orchestrator로 리팩토링

### Phase 3: Component Refactoring (Week 5-6)
1. [ ] MeetingDetailPage 컴포넌트 분리
2. [ ] TeamDetailPage 컴포넌트 분리
3. [ ] RemoteAudio 별도 파일로 분리
4. [ ] Custom hooks 추출 (useMeetingDetail, useTeamDetail)

### Phase 4: Store Optimization (Week 7-8)
1. [ ] meetingRoomStore 슬라이스 분리
2. [ ] teamStore 슬라이스 분리
3. [ ] Store composition 패턴 적용

### Phase 5: Polish (Week 9+)
1. [ ] Error Boundary 추가
2. [ ] Loading states 개선
3. [ ] Performance 최적화 (React.memo, useMemo)
4. [ ] 문서화

---

## 8. Metrics to Track

### 8.1 Code Quality Metrics

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Test Coverage | 0% | >70% | vitest --coverage |
| Largest File | 1,109 lines | <300 lines | wc -l |
| Avg File Size | 185 lines | <150 lines | wc -l / file count |
| Cyclomatic Complexity | N/A | <10 | eslint-plugin-complexity |

### 8.2 Runtime Metrics

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| First Load JS | TBD | <200KB | webpack-bundle-analyzer |
| Hook Re-renders | TBD | Minimize | React DevTools Profiler |

---

## 9. Appendix

### A. Complete File List with Line Counts

```
File                                         Lines
------------------------------------------------
hooks/useWebRTC.ts                           1109  [CRITICAL]
pages/MeetingDetailPage.tsx                   599  [HIGH]
pages/TeamDetailPage.tsx                      505  [HIGH]
services/recordingStorageService.ts           420  [MEDIUM]
components/meeting/MeetingRoom.tsx            384  [MEDIUM]
stores/teamStore.ts                           374  [MEDIUM]
stores/meetingRoomStore.ts                    320  [MEDIUM]
types/webrtc.ts                               289
services/webrtcService.ts                     221
hooks/useAudioLevel.ts                        221
components/meeting/AudioControls.tsx          216
services/api.ts                               187
components/meeting/ParticipantList.tsx        168
pages/HomePage.tsx                            162
components/meeting/RecordingList.tsx          155
services/recordingService.ts                  154
services/signalingService.ts                  135
stores/authStore.ts                           122
pages/MeetingRoomPage.tsx                     115
components/meeting/ScreenShareView.tsx        111
components/meeting/DeviceSelector.tsx         111
components/auth/RegisterForm.tsx              100
hooks/useAudioDevices.ts                       83
services/meetingService.ts                     79
components/meeting/VolumeSlider.tsx            71
App.tsx                                        69
services/teamService.ts                        64
components/auth/LoginForm.tsx                  63
components/ui/Button.tsx                       59
types/index.ts                                 40
pages/LoginPage.tsx                            35
components/ui/Input.tsx                        33
hooks/useAuth.ts                               32
pages/RegisterPage.tsx                         31
services/authService.ts                        23
main.tsx                                       18
vite-env.d.ts                                   1
------------------------------------------------
Total                                        6878
```

### B. Architecture Decision References

- [CLAUDE-decisions.md](../../CLAUDE-decisions.md) - D1: Mesh P2P, D2: Client-side Recording
- [CLAUDE-patterns.md](../../CLAUDE-patterns.md) - Zustand Selector Pattern, Recording Flow

### C. Related Backend Files

- `backend/app/services/signaling_service.py` - WebSocket signaling
- `backend/app/api/v1/endpoints/recordings.py` - Recording upload API
- `backend/app/core/webrtc_config.py` - ICE server configuration

---

**Report Generated by:** Claude Code Refactoring Analysis
**Analysis Date:** 2026-01-08
**Target:** frontend/ directory
