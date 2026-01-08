/**
 * Vitest 테스트 설정 파일
 * 전역 설정 및 모의 객체 정의
 */

import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll, vi } from 'vitest';

// 각 테스트 후 자동 cleanup
afterEach(() => {
  cleanup();
});

// localStorage 모의 객체 (실제 storage 기능 포함)
const createStorageMock = () => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
  };
};

Object.defineProperty(window, 'localStorage', {
  value: createStorageMock(),
});

Object.defineProperty(window, 'sessionStorage', {
  value: createStorageMock(),
});

// matchMedia 모의 객체 (Tailwind CSS 관련)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// ResizeObserver 모의 객체
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
});

// IntersectionObserver 모의 객체
class IntersectionObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  root = null;
  rootMargin = '';
  thresholds = [];
}

Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: IntersectionObserverMock,
});

// URL.createObjectURL 모의 객체
Object.defineProperty(URL, 'createObjectURL', {
  writable: true,
  value: vi.fn(() => 'blob:mock-url'),
});

Object.defineProperty(URL, 'revokeObjectURL', {
  writable: true,
  value: vi.fn(),
});

// MediaStream 모의 객체
class MediaStreamMock {
  id: string;
  active: boolean = true;
  private tracks: MediaStreamTrack[] = [];

  constructor(tracks?: MediaStreamTrack[]) {
    this.id = `stream-${Math.random().toString(36).slice(2)}`;
    if (tracks) {
      this.tracks = tracks;
    }
  }

  getTracks = () => [...this.tracks];
  getAudioTracks = () => this.tracks.filter((t) => t.kind === 'audio');
  getVideoTracks = () => this.tracks.filter((t) => t.kind === 'video');
  addTrack = (track: MediaStreamTrack) => {
    this.tracks.push(track);
  };
  removeTrack = (track: MediaStreamTrack) => {
    this.tracks = this.tracks.filter((t) => t.id !== track.id);
  };
  clone = () => new MediaStreamMock([...this.tracks]);
  getTrackById = (id: string) => this.tracks.find((t) => t.id === id) || null;
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  dispatchEvent = vi.fn().mockReturnValue(true);
  onaddtrack: ((ev: MediaStreamTrackEvent) => void) | null = null;
  onremovetrack: ((ev: MediaStreamTrackEvent) => void) | null = null;
}

Object.defineProperty(window, 'MediaStream', {
  writable: true,
  value: MediaStreamMock,
});

// MediaStreamTrack 모의 객체
const createMockTrack = (kind: 'audio' | 'video'): MediaStreamTrack => ({
  kind,
  id: `${kind}-track-${Math.random().toString(36).slice(2)}`,
  enabled: true,
  muted: false,
  readyState: 'live' as MediaStreamTrackState,
  label: `Mock ${kind} track`,
  contentHint: '',
  stop: vi.fn(),
  clone: vi.fn(),
  getSettings: vi.fn().mockReturnValue({}),
  getConstraints: vi.fn().mockReturnValue({}),
  getCapabilities: vi.fn().mockReturnValue({}),
  applyConstraints: vi.fn().mockResolvedValue(undefined),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn().mockReturnValue(true),
  onended: null,
  onmute: null,
  onunmute: null,
});

// navigator.mediaDevices 모의 객체 (WebRTC 테스트용)
const createMockStreamWithTracks = (hasAudio = true, hasVideo = false) => {
  const tracks: MediaStreamTrack[] = [];
  if (hasAudio) tracks.push(createMockTrack('audio'));
  if (hasVideo) tracks.push(createMockTrack('video'));
  return new MediaStreamMock(tracks);
};

const mediaDevicesMock = {
  getUserMedia: vi.fn().mockImplementation(async (constraints?: MediaStreamConstraints) => {
    const hasAudio = !!constraints?.audio;
    const hasVideo = !!constraints?.video;
    return createMockStreamWithTracks(hasAudio || true, hasVideo);
  }),
  getDisplayMedia: vi.fn().mockImplementation(async () => {
    return createMockStreamWithTracks(false, true);
  }),
  enumerateDevices: vi.fn().mockResolvedValue([
    { deviceId: 'default-audio-input', kind: 'audioinput', label: 'Default Microphone', groupId: 'group1' },
    { deviceId: 'default-audio-output', kind: 'audiooutput', label: 'Default Speaker', groupId: 'group1' },
    { deviceId: 'default-video-input', kind: 'videoinput', label: 'Default Camera', groupId: 'group2' },
  ]),
};

Object.defineProperty(navigator, 'mediaDevices', {
  writable: true,
  value: mediaDevicesMock,
});

// RTCPeerConnection 모의 객체
class RTCPeerConnectionMock {
  localDescription: RTCSessionDescriptionInit | null = null;
  remoteDescription: RTCSessionDescriptionInit | null = null;
  connectionState: RTCPeerConnectionState = 'new';
  iceConnectionState: RTCIceConnectionState = 'new';
  signalingState: RTCSignalingState = 'stable';

  onicecandidate: ((event: RTCPeerConnectionIceEvent) => void) | null = null;
  ontrack: ((event: RTCTrackEvent) => void) | null = null;
  onconnectionstatechange: (() => void) | null = null;

  createOffer = vi.fn().mockResolvedValue({ type: 'offer', sdp: 'mock-sdp' });
  createAnswer = vi.fn().mockResolvedValue({ type: 'answer', sdp: 'mock-sdp' });
  setLocalDescription = vi.fn().mockResolvedValue(undefined);
  setRemoteDescription = vi.fn().mockResolvedValue(undefined);
  addIceCandidate = vi.fn().mockResolvedValue(undefined);
  addTrack = vi.fn().mockReturnValue({});
  getSenders = vi.fn().mockReturnValue([]);
  close = vi.fn();
}

Object.defineProperty(window, 'RTCPeerConnection', {
  writable: true,
  value: RTCPeerConnectionMock,
});

// RTCSessionDescription 모의 객체
class RTCSessionDescriptionMock {
  type: RTCSdpType;
  sdp: string;

  constructor(init?: RTCSessionDescriptionInit) {
    this.type = init?.type || 'offer';
    this.sdp = init?.sdp || '';
  }
}

Object.defineProperty(window, 'RTCSessionDescription', {
  writable: true,
  value: RTCSessionDescriptionMock,
});

// RTCIceCandidate 모의 객체
class RTCIceCandidateMock {
  candidate: string;
  sdpMid: string | null;
  sdpMLineIndex: number | null;

  constructor(init?: RTCIceCandidateInit) {
    this.candidate = init?.candidate || '';
    this.sdpMid = init?.sdpMid || null;
    this.sdpMLineIndex = init?.sdpMLineIndex ?? null;
  }

  toJSON() {
    return {
      candidate: this.candidate,
      sdpMid: this.sdpMid,
      sdpMLineIndex: this.sdpMLineIndex,
    };
  }
}

Object.defineProperty(window, 'RTCIceCandidate', {
  writable: true,
  value: RTCIceCandidateMock,
});

// MediaRecorder 모의 객체
class MediaRecorderMock {
  state: 'inactive' | 'recording' | 'paused' = 'inactive';
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}

  start = vi.fn(() => {
    this.state = 'recording';
  });

  stop = vi.fn(() => {
    this.state = 'inactive';
    if (this.onstop) {
      this.onstop();
    }
  });

  pause = vi.fn(() => {
    this.state = 'paused';
  });

  resume = vi.fn(() => {
    this.state = 'recording';
  });

  static isTypeSupported = vi.fn().mockReturnValue(true);
}

Object.defineProperty(window, 'MediaRecorder', {
  writable: true,
  value: MediaRecorderMock,
});

// AudioContext 모의 객체
class AudioContextMock {
  state: AudioContextState = 'running';
  destination = {};

  createMediaStreamSource = vi.fn().mockReturnValue({
    connect: vi.fn(),
    disconnect: vi.fn(),
  });

  createMediaStreamDestination = vi.fn().mockReturnValue({
    stream: {
      getTracks: () => [],
      getAudioTracks: () => [],
    },
  });

  createGain = vi.fn().mockReturnValue({
    gain: { value: 1 },
    connect: vi.fn(),
    disconnect: vi.fn(),
  });

  createAnalyser = vi.fn().mockReturnValue({
    fftSize: 256,
    frequencyBinCount: 128,
    getByteFrequencyData: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  });

  resume = vi.fn().mockResolvedValue(undefined);
  close = vi.fn().mockResolvedValue(undefined);
}

Object.defineProperty(window, 'AudioContext', {
  writable: true,
  value: AudioContextMock,
});

// IndexedDB 모의 객체 (fake-indexeddb는 별도 설치 필요시 사용)
beforeAll(() => {
  // IndexedDB 기본 모의 객체
  const indexedDBMock = {
    open: vi.fn().mockReturnValue({
      onerror: null,
      onsuccess: null,
      onupgradeneeded: null,
      result: {
        objectStoreNames: { contains: vi.fn().mockReturnValue(false) },
        createObjectStore: vi.fn().mockReturnValue({
          createIndex: vi.fn(),
        }),
        transaction: vi.fn().mockReturnValue({
          objectStore: vi.fn().mockReturnValue({
            put: vi.fn(),
            get: vi.fn(),
            delete: vi.fn(),
            getAll: vi.fn(),
            index: vi.fn().mockReturnValue({
              getAll: vi.fn(),
            }),
          }),
          oncomplete: null,
          onerror: null,
        }),
      },
    }),
    deleteDatabase: vi.fn(),
  };

  Object.defineProperty(window, 'indexedDB', {
    writable: true,
    value: indexedDBMock,
  });
});

// WebSocket 모의 객체
class WebSocketMock {
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    // 비동기로 연결 완료 시뮬레이션
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = WebSocket.CLOSED;
  });
}

Object.defineProperty(window, 'WebSocket', {
  writable: true,
  value: WebSocketMock,
});
