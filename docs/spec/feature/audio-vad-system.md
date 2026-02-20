# Audio & VAD 시스템

## 요약

Mit은 **음성 중심 회의 시스템**으로, 고품질 오디오 처리와 실시간 발화 감지를 핵심으로 한다. 클라이언트 사이드 VAD(Voice Activity Detection)를 통해 각 참여자의 발화를 정확히 감지하고, Web Audio API 기반 세밀한 오디오 제어를 제공한다.

---

## 핵심 개념

### 1. Audio-Only Conferencing

Mit은 화상회의가 아닌 **오디오 전용 회의**에 최적화되어 있다.

**설계 철학**
- 영상 없이 음성만으로 고품질 커뮤니케이션
- 네트워크 대역폭 최소화 (오디오만 전송)
- 낮은 지연시간 (LiveKit SFU 기반)
- 참여자별 독립적인 오디오 스트림 관리

### 2. Client-Side VAD

각 참여자의 클라이언트에서 VAD를 수행하여 발화 이벤트를 서버로 전송한다.

**왜 클라이언트 VAD인가?**
- **낮은 지연**: 서버 전송 없이 즉시 발화 감지
- **서버 부하 감소**: 오디오 데이터를 서버로 보내지 않음
- **정확한 타이밍**: 실제 발화 시점을 ms 단위로 캡처
- **프라이버시**: 오디오 데이터가 VAD 처리를 위해 서버로 전송되지 않음

**VAD 결과 활용**
- STT 트리거: 발화 구간만 서버 STT 처리 (향후)
- 화자 분리: 발화 타이밍 기반 화자 구분
- 발화 통계: 각 참여자의 발화 시간/빈도 분석

### 3. Web Audio API 기반 제어

마이크 게인과 참여자별 볼륨을 Web Audio API의 GainNode로 제어한다.

**이점**
- **정밀한 볼륨 제어**: 0~200% 범위, 20% 단위 조절
- **실시간 조정**: 회의 중 즉시 변경 가능
- **참여자별 독립**: 각 참여자 볼륨을 개별 조정
- **설정 지속**: localStorage에 캐싱하여 회의 간 유지

---

## 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                      MeetingRoom                             │
│                                                              │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐   │
│  │   useLiveKit   │──────│   useVAD   │      │useAudioDevices│   │
│  └─────┬──────┘      └─────┬──────┘      └─────┬──────┘   │
│        │                   │                   │            │
│        │                   │                   │            │
│  ┌─────▼──────────────────▼──────────────────▼─────┐      │
│  │                                                   │      │
│  │            meetingRoomStore                       │      │
│  │        (Zustand - Global State)                   │      │
│  │                                                   │      │
│  │  - localStream                                    │      │
│  │  - remoteStreams (Map<userId, MediaStream>)      │      │
│  │  - micGain (0.0 ~ 2.0)                           │      │
│  │  - remoteVolumes (Map<userId, volume>)           │      │
│  │  - audioInputDeviceId                             │      │
│  │  - audioOutputDeviceId                            │      │
│  │                                                   │      │
│  └───────────────────────┬───────────────────────────┘      │
│                          │                                  │
│                          ▼                                  │
│              audioSettingsStorage.ts                        │
│            (localStorage persistence)                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### VAD 처리 흐름

```
┌──────────────────────────────────────────────────────────────┐
│                    Client-Side VAD                            │
└──────────────────────────────────────────────────────────────┘

[마이크 입력] → [MediaStream]
                      │
                      ▼
              ┌───────────────┐
              │  Web Audio    │
              │  GainNode     │  ← micGain (0.0 ~ 2.0)
              │  (게인 처리)   │
              └───────┬───────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
  ┌─────────┐              ┌────────────────┐
  │LiveKit  │              │  Silero VAD    │
  │Publish  │              │(@ricky0123/    │
  │         │              │  vad-web)      │
  └─────────┘              └────────┬───────┘
                                    │
                    ┌───────────────┴────────────────┐
                    │                                │
                    ▼                                ▼
            ┌───────────────┐              ┌────────────────┐
            │ Speech Start  │              │  Speech End    │
            │   Callback    │              │   Callback     │
            └───────┬───────┘              └────────┬───────┘
                    │                                │
                    └────────────┬───────────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │  DataPacket 전송       │
                    │  (LiveKit)             │
                    │                        │
                    │  type: 'vad_event'     │
                    │  payload: {            │
                    │    eventType,          │
                    │    segmentStartMs,     │
                    │    segmentEndMs,       │
                    │    timestamp           │
                    │  }                     │
                    └───────────┬────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │   Backend    │
                        │  (VAD 수집)   │
                        └──────────────┘
```

### 원격 오디오 재생 흐름

```
┌──────────────────────────────────────────────────────────────┐
│                  Remote Audio Playback                        │
└──────────────────────────────────────────────────────────────┘

[LiveKit Subscribe] → [RemoteTrack]
                           │
                           ▼
                    [MediaStream]
                           │
                           ▼
               ┌───────────────────────┐
               │  Web Audio API        │
               │                       │
               │  Source → GainNode    │ ← remoteVolumes[userId]
               │           ↓           │
               │     AudioContext      │
               │       .destination    │
               └───────────────────────┘
                           │
                           ▼
                   [HTMLAudioElement]
                   (muted, display:none)
                           │
                           ▼
                   [setSinkId()]
                   audioOutputDeviceId
                           │
                           ▼
                      [스피커 출력]
```

---

## VAD 상세

### 1. Silero VAD

**기술 스택**
- 라이브러리: `@ricky0123/vad-web` (v0.0.20)
- 모델: Silero VAD (ONNX WebAssembly)
- 실행 환경: 클라이언트 브라우저 (WebAssembly)

**VAD 설정 (useVAD.ts)**

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `positiveSpeechThreshold` | 0.5 | 발화 시작 감지 임계값 (Silero 공식 권장값) |
| `negativeSpeechThreshold` | 0.35 | 발화 종료 감지 임계값 (positiveSpeechThreshold - 0.15) |
| `minSpeechMs` | 50 | 최소 발화 길이 (50ms, LiveKit 최소값) |
| `preSpeechPadMs` | 30 | 발화 시작 전 패딩 (30ms, @ricky0123/vad 최소 권장값) |
| `redemptionMs` | 500 | 발화 종료 유예 시간 (빠른 응답 최적화) |

**설정 근거**
- `positiveSpeechThreshold=0.5`: Silero 공식 권장값, 일반적인 환경에서 최적 감도
- `minSpeechMs=50`: LiveKit 에이전트 최소값, 짧은 발화도 감지
- `redemptionMs=500`: 짧은 무음(예: 숨 쉬기)을 발화 중단으로 인식하지 않음

### 2. VAD 메타데이터

```typescript
interface VADMetadata {
  segments: VADSegment[];          // 발화 구간 목록
  totalDurationMs: number;         // VAD 전체 실행 시간
  settings: {
    positiveSpeechThreshold: number;
    negativeSpeechThreshold: number;
    minSpeechMs: number;
    preSpeechPadMs: number;
    redemptionMs: number;
  };
}

interface VADSegment {
  startMs: number;  // 발화 시작 시간 (VAD 시작 기준, ms)
  endMs: number;    // 발화 종료 시간 (VAD 시작 기준, ms)
}
```

**수집 시점**
- 발화 시작: `onSpeechStart` 콜백 트리거
- 발화 종료: `onSpeechEnd` 콜백 트리거
- 회의 종료: `stopVAD()` 호출 시 전체 메타데이터 반환

**활용**
- STT 최적화: 발화 구간만 서버 STT 처리 (향후)
- 화자 분리: 발화 타이밍 기반 화자 분류
- 참여도 분석: 각 참여자의 발화 시간/빈도 통계

### 3. DataPacket 전송

VAD 이벤트를 LiveKit DataPacket으로 실시간 전송한다.

**메시지 포맷**
```typescript
{
  type: 'vad_event',
  payload: {
    eventType: 'speech_start' | 'speech_end',
    segmentStartMs?: number,
    segmentEndMs?: number,
    timestamp: string  // ISO 8601
  }
}
```

**전송 조건**
- `speech_start`: 발화 시작 즉시 전송 (reliable=true)
- `speech_end`: 발화 종료 시 세그먼트 정보와 함께 전송

**서버 처리**
- 백엔드는 DataPacket을 수신하여 발화 이벤트 로깅
- 향후 실시간 STT 트리거로 활용 예정

---

## 오디오 제어

### 1. 마이크 게인 (Mic Gain)

**구현 방식**
- Web Audio API의 `GainNode` 사용
- 원본 오디오 스트림 → GainNode → 처리된 스트림
- 처리된 스트림을 LiveKit에 publish 및 VAD에 전달

**코드 흐름 (useLiveKit.ts)**
```typescript
// 1. 원본 오디오 트랙 생성
const audioTrack = await createLocalTracks({ audio: true });

// 2. Web Audio 노드 생성
audioContext = new AudioContext();
source = audioContext.createMediaStreamSource(originalStream);
gainNode = audioContext.createGain();
destination = audioContext.createMediaStreamDestination();

// 3. 게인 설정 및 연결
gainNode.gain.value = micGain;  // 0.0 ~ 2.0
source.connect(gainNode);
gainNode.connect(destination);

// 4. 처리된 스트림 사용
const processedStream = destination.stream;
await vad.startVAD(processedStream);
await room.localParticipant.publishTrack(audioTrack);
```

**게인 범위**
- 최소: 0.0 (음소거)
- 기본: 1.0 (100%)
- 최대: 2.0 (200%)
- 조절 단위: 20% (0.2)

**UI 컨트롤 (AudioControls.tsx)**
- Range 슬라이더: 0~200%, 20% 단위
- 실시간 조정: 회의 중 즉시 반영
- 시각적 피드백: 현재 게인 값 백분율 표시 (예: "120%")

### 2. 참여자별 볼륨 (Remote Volume)

**구현 방식**
- 각 원격 참여자마다 독립적인 Web Audio 파이프라인 생성
- `RemoteAudio` 컴포넌트가 참여자별 볼륨 관리

**코드 흐름 (RemoteAudio.tsx)**
```typescript
// 1. 원격 스트림 수신
const remoteStream = remoteStreams.get(userId);

// 2. Web Audio 파이프라인 생성
audioContext = new AudioContext();
source = audioContext.createMediaStreamSource(remoteStream);
gainNode = audioContext.createGain();

// 3. 볼륨 설정
gainNode.gain.value = volume;  // 0.0 ~ 2.0

// 4. 연결
source.connect(gainNode);
gainNode.connect(audioContext.destination);

// 5. HTMLAudioElement는 음소거 (Web Audio API가 실제 출력 담당)
audioElement.muted = true;
```

**볼륨 범위**
- 최소: 0.0 (음소거)
- 기본: 1.0 (100%)
- 최대: 2.0 (200%)
- 조절 단위: 임의 (슬라이더 연속 조정)

**UI 컨트롤 (VolumeSlider.tsx)**
- Range 슬라이더: 0~200%
- 아이콘 변화: 볼륨 0 (음소거), <50% (작음), ≥50% (큼)
- 퍼센트 표시: tabular-nums 폰트로 정렬

### 3. 오디오 장치 선택

**마이크 선택 (Audio Input)**
- `useAudioDevices` 훅으로 장치 목록 조회
- `navigator.mediaDevices.enumerateDevices()` 사용
- 장치 변경 시 트랙 교체 (unpublish → publish)

**스피커 선택 (Audio Output)**
- `HTMLAudioElement.setSinkId()` API 사용
- 브라우저 지원 체크: Chrome, Edge 지원 / Firefox, Safari 미지원
- 미지원 시 UI에 "(미지원)" 표시

**장치 변경 감지**
- `navigator.mediaDevices.addEventListener('devicechange')`
- 장치 연결/해제 시 목록 자동 갱신
- 레이블 없음: 권한 미허용 시 "마이크 1", "스피커 2" 등 기본 이름 표시

---

## 설정 지속성 (Persistence)

### localStorage 캐싱

**저장 항목 (audioSettingsStorage.ts)**
```typescript
interface AudioSettings {
  micGain: number;
  audioInputDeviceId: string | null;
  audioOutputDeviceId: string | null;
}

// 참여자별 볼륨 (별도 저장)
remoteVolumes: Map<userId, volume>
```

**저장 시점**
- 마이크 게인 변경 시
- 마이크 장치 변경 시
- 스피커 장치 변경 시
- 참여자 볼륨 변경 시

**로드 시점**
- 앱 초기화 시: `meetingRoomStore` 생성 시 캐시 로드
- 회의 참여 시: 캐시된 설정 자동 적용

**장점**
- **일관된 경험**: 회의마다 설정을 재조정할 필요 없음
- **참여자별 기억**: 특정 참여자의 볼륨 설정이 회의 간 유지됨
- **장치 기억**: 이전에 선택한 마이크/스피커 자동 선택

**localStorage 키**
- `mit-audio-settings`: 마이크 게인, 장치 ID
- `mit-remote-volumes`: 참여자별 볼륨 (JSON 직렬화)

---

## 통합: LiveKit + VAD + Audio Controls

### 1. 회의 참여 시 (joinRoom)

```
1. LiveKit 토큰 획득
2. Room 연결
3. 로컬 오디오 트랙 생성
   - 캐시된 audioInputDeviceId 사용
   - 캐시된 micGain으로 GainNode 설정
4. VAD 시작
   - 게인 처리된 스트림을 VAD에 전달
5. 트랙 publish
   - 게인 처리된 오디오를 LiveKit에 publish
6. 자동 녹음 시작
```

### 2. 원격 참여자 트랙 구독 시

```
1. LiveKit TrackSubscribed 이벤트 수신
2. RemoteTrack → MediaStream 변환
3. remoteStreams Map에 저장
4. RemoteAudio 컴포넌트 렌더링
   - Web Audio 파이프라인 생성
   - 캐시된 remoteVolumes[userId] 적용
   - audioOutputDeviceId로 setSinkId 설정
```

### 3. VAD 이벤트 처리

```
1. useVAD 훅에서 발화 감지
2. isSpeaking 상태 변경
3. useLiveKit의 useEffect에서 감지
4. DataPacket으로 서버 전송
   - speech_start: segmentStartMs 포함
   - speech_end: segmentStartMs, segmentEndMs 포함
```

### 4. 설정 변경 시

```
[마이크 게인 변경]
1. changeMicGain(gain) 호출
2. gainNode.gain.value 업데이트
3. meetingRoomStore.setMicGain(gain)
4. audioSettingsStorage.saveAudioSettings()

[마이크 장치 변경]
1. changeAudioInputDevice(deviceId) 호출
2. 새 트랙 생성 (deviceId 지정)
3. 게인 처리 스트림 재생성
4. 기존 트랙 unpublish
5. 새 트랙 publish
6. VAD 재시작
7. meetingRoomStore.setAudioInputDeviceId(deviceId)
8. audioSettingsStorage.saveAudioSettings()

[참여자 볼륨 변경]
1. changeRemoteVolume(userId, volume) 호출
2. meetingRoomStore.setRemoteVolume(userId, volume)
3. audioSettingsStorage.saveRemoteVolumes()
4. RemoteAudio 컴포넌트의 useEffect 트리거
5. gainNode.gain.value 업데이트
```

---

## UI 컴포넌트

### 1. AudioControls.tsx

회의실 하단에 표시되는 메인 오디오 컨트롤 패널.

**구성 요소**
- 마이크 게인 슬라이더 (가장 왼쪽)
- 마이크 장치 선택 드롭다운
- 마이크 음소거 토글 버튼 (중앙, 크게)
- 스피커 장치 선택 드롭다운
- 화면공유 토글 버튼 (오른쪽)

**시각적 피드백**
- 음소거 시: 버튼 빨간색 배경 + 음소거 아이콘
- 마이크 켜짐: 버튼 회색 배경 + 마이크 아이콘
- 화면공유 중: 버튼 초록색 배경 + 중지 아이콘

### 2. DeviceSelector.tsx

오디오 장치 선택 드롭다운.

**특징**
- 아이콘 + 드롭다운 콤보
- 장치 목록 동적 로딩 (`useAudioDevices`)
- 장치 연결/해제 시 자동 갱신
- 미지원 브라우저 처리 (스피커 선택 시)

### 3. VolumeSlider.tsx

원격 참여자 볼륨 조절 슬라이더.

**특징**
- 아이콘 + 슬라이더 + 퍼센트 표시
- 볼륨에 따라 아이콘 변화 (음소거, 작음, 큼)
- tabular-nums 폰트로 숫자 정렬
- 0~200% 범위 조절

### 4. RemoteAudio.tsx

원격 참여자 오디오 재생 컴포넌트 (숨김).

**역할**
- Web Audio 파이프라인 생성 및 관리
- 볼륨 조절 (GainNode)
- 출력 장치 선택 (setSinkId)
- HTMLAudioElement 렌더링 (display:none)

**생명주기**
- 마운트: Web Audio 파이프라인 생성
- 볼륨 변경: gainNode.gain.value 업데이트
- 언마운트: AudioContext.close(), 리소스 정리

---

## 기술적 고려사항

### 1. AudioContext State 관리

**문제**: 브라우저 정책으로 인해 AudioContext가 suspended 상태로 생성될 수 있음

**해결**
```typescript
if (audioContext.state === 'suspended') {
  await audioContext.resume();
}
```

**적용 위치**
- `RemoteAudio.tsx`: 원격 오디오 재생 시
- `useLiveKit.ts`: 로컬 스트림 생성 시

### 2. LiveKit SDK 트랙 관리

**주의사항**: LiveKit SDK가 트랙 생명주기를 관리하므로, 수동으로 `track.stop()`을 호출하면 안 됨

**올바른 정리 방법**
- 로컬 트랙: `room.localParticipant.unpublishTrack()`
- 원격 트랙: SDK가 자동 정리, 앱에서는 Map에서만 제거

**코드 (meetingRoomStore.ts)**
```typescript
removeRemoteStream: (userId) => {
  const stream = remoteStreams.get(userId);
  if (stream) {
    // track.stop()을 호출하지 않음!
    // LiveKit SDK가 관리하며, stop()을 호출하면 재접속 시 문제 발생
    remoteStreams.delete(userId);
  }
}
```

### 3. Strict Mode 대응

**문제**: React Strict Mode에서 컴포넌트가 2번 마운트되어 중복 연결 시도

**해결 (useLiveKit.ts)**
```typescript
const abortControllerRef = useRef<AbortController | null>(null);

useEffect(() => {
  return () => {
    // 진행 중인 연결 시도 취소
    abortControllerRef.current?.abort();
    // 실제 연결된 경우 정리
    if (roomRef.current) {
      room.disconnect();
    }
  };
}, []);
```

### 4. 마이크 장치 변경 시 VAD 재시작

**이유**: VAD가 기존 스트림에 바인딩되어 있어, 장치 변경 시 새 스트림으로 재시작 필요

**코드 (useLiveKit.ts)**
```typescript
const changeAudioInputDevice = async (deviceId: string) => {
  // 1. 새 트랙 생성
  const newAudioTrack = await createLocalTracks({ audio: { deviceId } });

  // 2. 게인 처리된 스트림 생성
  const processedStream = await createProcessedStream(originalStream, micGain);

  // 3. 기존 트랙 교체
  await room.localParticipant.unpublishTrack(existingTrack);
  await room.localParticipant.publishTrack(newAudioTrack);

  // 4. VAD 재시작
  vad.stopVAD();
  vadStartTimeRef.current = Date.now();
  await vad.startVAD(processedStream);
};
```

---

## 향후 확장

### 1. 실시간 STT 통합

**계획**
- VAD 이벤트를 STT 트리거로 활용
- 발화 구간만 서버로 전송하여 STT 처리
- 네트워크 대역폭 절약 + STT 정확도 향상

**필요 작업**
- 발화 구간 오디오 버퍼 캡처 (AudioWorklet)
- 서버 WebSocket 연결 (실시간 전송)
- STT 결과 실시간 표시

### 2. 화자 분리 (Speaker Diarization)

**계획**
- VAD 타이밍 + 음성 특징 추출 (MFCC, Mel-spectrogram)
- 클러스터링으로 화자 분류
- 각 발화에 화자 ID 자동 태깅

**필요 작업**
- 오디오 특징 추출 파이프라인
- 화자 임베딩 모델 (예: Resemblyzer)
- 화자 변경 감지 알고리즘

### 3. 소음 제거 (Noise Suppression)

**계획**
- RNNoise 또는 Krisp AI 기반 소음 제거
- Web Audio API AudioWorklet으로 실시간 처리
- 회의 품질 향상 (키보드 타이핑, 배경 소음 제거)

**필요 작업**
- RNNoise WASM 모듈 통합
- AudioWorklet 프로세서 구현
- CPU 사용량 최적화

### 4. 오디오 분석 대시보드

**계획**
- 각 참여자의 발화 시간/빈도 통계
- 참여도 분석 (발화 비율, 침묵 시간)
- 회의 패턴 분석 (중첩 발화, 발화 순서)

**필요 작업**
- VAD 메타데이터 집계 로직
- 시각화 컴포넌트 (차트)
- 실시간 업데이트 UI

---

## 참조

### 외부 라이브러리

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| `livekit-client` | ^2.0.0 | LiveKit SFU 클라이언트 SDK |
| `@ricky0123/vad-web` | ^0.0.20 | Silero VAD (ONNX WebAssembly) |
| `zustand` | ^4.0.0 | 전역 상태 관리 (meetingRoomStore) |

### 핵심 파일

**Frontend**
- `frontend/src/hooks/useVAD.ts`: VAD 훅
- `frontend/src/hooks/useAudioDevices.ts`: 오디오 장치 목록 훅
- `frontend/src/hooks/useLiveKit.ts`: LiveKit 연결 및 오디오 관리
- `frontend/src/stores/meetingRoomStore.ts`: 회의실 상태 (Zustand)
- `frontend/src/utils/audioSettingsStorage.ts`: localStorage 캐싱
- `frontend/src/components/meeting/AudioControls.tsx`: 오디오 컨트롤 UI
- `frontend/src/components/meeting/DeviceSelector.tsx`: 장치 선택 드롭다운
- `frontend/src/components/meeting/VolumeSlider.tsx`: 볼륨 슬라이더
- `frontend/src/components/meeting/RemoteAudio.tsx`: 원격 오디오 재생

**Backend**
- `backend/api/v1/endpoints/livekit_webhooks.py`: LiveKit 웹훅 (VAD 이벤트 수신)
- `backend/services/livekit_service.py`: LiveKit 토큰 생성

### 관련 문서

- LiveKit Docs: https://docs.livekit.io/
- Silero VAD: https://github.com/snakers4/silero-vad
- @ricky0123/vad-web: https://github.com/ricky0123/vad
- Web Audio API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
