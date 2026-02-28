/**
 * 테스트 인프라 검증용 smoke test
 * 모든 mock이 올바르게 설정되었는지 확인
 */

describe('Test Infrastructure', () => {
  describe('Global Mocks', () => {
    it('should have localStorage mock', () => {
      localStorage.setItem('test', 'value');
      expect(localStorage.getItem('test')).toBe('value');
      localStorage.removeItem('test');
      expect(localStorage.getItem('test')).toBeNull();
    });

    it('should have matchMedia mock', () => {
      const mql = window.matchMedia('(min-width: 768px)');
      expect(mql.matches).toBe(false);
      expect(typeof mql.addEventListener).toBe('function');
    });

    it('should have ResizeObserver mock', () => {
      const observer = new ResizeObserver(() => {});
      expect(typeof observer.observe).toBe('function');
      expect(typeof observer.disconnect).toBe('function');
    });

    it('should have IntersectionObserver mock', () => {
      const observer = new IntersectionObserver(() => {});
      expect(typeof observer.observe).toBe('function');
      expect(typeof observer.disconnect).toBe('function');
    });
  });

  describe('Media API Mocks', () => {
    it('should have URL.createObjectURL mock', () => {
      const blob = new Blob(['test']);
      const url = URL.createObjectURL(blob);
      expect(url).toMatch(/^blob:/);
      URL.revokeObjectURL(url);
    });

    it('should have navigator.mediaDevices mock', async () => {
      expect(navigator.mediaDevices).toBeDefined();
      expect(typeof navigator.mediaDevices.getUserMedia).toBe('function');
      expect(typeof navigator.mediaDevices.getDisplayMedia).toBe('function');
      expect(typeof navigator.mediaDevices.enumerateDevices).toBe('function');
    });

    it('should getUserMedia return mock stream', async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      expect(stream).toBeDefined();
      expect(stream.getTracks().length).toBeGreaterThan(0);
    });

    it('should enumerateDevices return mock devices', async () => {
      const devices = await navigator.mediaDevices.enumerateDevices();
      expect(devices.length).toBeGreaterThan(0);
      expect(devices.some((d) => d.kind === 'audioinput')).toBe(true);
    });
  });

  describe('WebRTC Mocks', () => {
    it('should have RTCPeerConnection mock', () => {
      const pc = new RTCPeerConnection();
      expect(pc).toBeDefined();
      expect(typeof pc.createOffer).toBe('function');
      expect(typeof pc.createAnswer).toBe('function');
      expect(typeof pc.setLocalDescription).toBe('function');
      expect(typeof pc.setRemoteDescription).toBe('function');
      expect(typeof pc.addIceCandidate).toBe('function');
      expect(typeof pc.close).toBe('function');
    });

    it('should have RTCSessionDescription mock', () => {
      const desc = new RTCSessionDescription({ type: 'offer', sdp: 'mock-sdp' });
      expect(desc.type).toBe('offer');
      expect(desc.sdp).toBe('mock-sdp');
    });

    it('should have RTCIceCandidate mock', () => {
      const candidate = new RTCIceCandidate({
        candidate: 'candidate:mock',
        sdpMid: '0',
        sdpMLineIndex: 0,
      });
      expect(candidate.candidate).toBe('candidate:mock');
    });
  });

  describe('MediaRecorder Mock', () => {
    it('should have MediaRecorder mock', () => {
      const stream = new MediaStream();
      const recorder = new MediaRecorder(stream);
      expect(recorder).toBeDefined();
      expect(typeof recorder.start).toBe('function');
      expect(typeof recorder.stop).toBe('function');
      expect(typeof recorder.pause).toBe('function');
      expect(typeof recorder.resume).toBe('function');
    });

    it('should support isTypeSupported', () => {
      expect(MediaRecorder.isTypeSupported('audio/webm')).toBe(true);
    });
  });

  describe('AudioContext Mock', () => {
    it('should have AudioContext mock', () => {
      const ctx = new AudioContext();
      expect(ctx).toBeDefined();
      expect(typeof ctx.createMediaStreamSource).toBe('function');
      expect(typeof ctx.createGain).toBe('function');
      expect(typeof ctx.createMediaStreamDestination).toBe('function');
    });

    it('should create gain node with proper methods', () => {
      const ctx = new AudioContext();
      const gain = ctx.createGain();
      expect(gain.gain.value).toBe(1);
      expect(typeof gain.connect).toBe('function');
      expect(typeof gain.disconnect).toBe('function');
    });
  });

  describe('IndexedDB Mock', () => {
    it('should have indexedDB mock', () => {
      expect(indexedDB).toBeDefined();
      expect(typeof indexedDB.open).toBe('function');
    });
  });

  describe('WebSocket Mock', () => {
    it('should have WebSocket mock', () => {
      const ws = new WebSocket('ws://localhost:8000/test');
      expect(ws).toBeDefined();
      expect(typeof ws.send).toBe('function');
      expect(typeof ws.close).toBe('function');
    });
  });
});
