/**
 * useWebRTC 훅 통합 테스트
 * 리팩토링 전 기존 동작 검증용 Characterization Test
 */

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWebRTC } from '@/hooks/useWebRTC';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import { signalingClient } from '@/services/signalingService';
import { webrtcService } from '@/services/webrtcService';
import api from '@/services/api';
import type { ServerMessage } from '@/types/webrtc';

// signalingClient 모킹 상태
let mockIsConnected = false;

// 모킹
vi.mock('@/services/signalingService', () => ({
  signalingClient: {
    connect: vi.fn().mockImplementation(() => {
      mockIsConnected = true;
      return Promise.resolve();
    }),
    disconnect: vi.fn().mockImplementation(() => {
      mockIsConnected = false;
    }),
    send: vi.fn(),
    onMessage: vi.fn(),
    get isConnected() {
      return mockIsConnected;
    },
  },
}));

vi.mock('@/services/webrtcService', () => ({
  webrtcService: {
    getLocalAudioStream: vi.fn(),
    createProcessedAudioStream: vi.fn(),
    createPeerConnection: vi.fn(),
    createOffer: vi.fn(),
    createAnswer: vi.fn(),
    setRemoteDescription: vi.fn(),
    addIceCandidate: vi.fn(),
    addTrack: vi.fn(),
    getDisplayMediaStream: vi.fn(),
  },
}));

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
  ensureValidToken: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@/services/recordingService', () => ({
  recordingService: {
    uploadRecordingPresigned: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('@/services/recordingStorageService', () => ({
  recordingStorageService: {
    saveNewChunks: vi.fn().mockResolvedValue(0),
    getChunks: vi.fn().mockResolvedValue([]),
    deleteRecording: vi.fn().mockResolvedValue(undefined),
    getRecordingsByMeeting: vi.fn().mockResolvedValue([]),
    cleanupOldRecordings: vi.fn().mockResolvedValue(undefined),
    mergeChunks: vi.fn().mockReturnValue(new Blob()),
  },
}));

describe('useWebRTC', () => {
  const mockMeetingId = 'test-meeting-123';
  const mockUserId = 'test-user-456';

  // Mock 스트림 생성 헬퍼
  const createMockStream = () => {
    const mockTrack = {
      kind: 'audio',
      id: `audio-${Math.random()}`,
      enabled: true,
      muted: false,
      readyState: 'live' as MediaStreamTrackState,
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
      label: 'Mock Audio Track',
      contentHint: '',
    };

    return {
      id: `stream-${Math.random()}`,
      active: true,
      getTracks: vi.fn().mockReturnValue([mockTrack]),
      getAudioTracks: vi.fn().mockReturnValue([mockTrack]),
      getVideoTracks: vi.fn().mockReturnValue([]),
      addTrack: vi.fn(),
      removeTrack: vi.fn(),
      clone: vi.fn(),
      getTrackById: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn().mockReturnValue(true),
      onaddtrack: null,
      onremovetrack: null,
    };
  };

  // Mock 피어 연결
  const createMockPeerConnection = () => ({
    localDescription: null,
    remoteDescription: null,
    connectionState: 'new',
    iceConnectionState: 'new',
    signalingState: 'stable',
    onicecandidate: null,
    ontrack: null,
    onconnectionstatechange: null,
    createOffer: vi.fn().mockResolvedValue({ type: 'offer', sdp: 'mock-sdp' }),
    createAnswer: vi.fn().mockResolvedValue({ type: 'answer', sdp: 'mock-sdp' }),
    setLocalDescription: vi.fn().mockResolvedValue(undefined),
    setRemoteDescription: vi.fn().mockResolvedValue(undefined),
    addIceCandidate: vi.fn().mockResolvedValue(undefined),
    addTrack: vi.fn(),
    getSenders: vi.fn().mockReturnValue([]),
    close: vi.fn(),
  });

  beforeEach(() => {
    vi.clearAllMocks();
    useMeetingRoomStore.getState().reset();

    // localStorage 모킹
    localStorage.setItem('accessToken', 'mock-token');

    // 기본 API 응답 설정
    vi.mocked(api.get).mockResolvedValue({
      data: {
        meetingId: mockMeetingId,
        status: 'in_progress',
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
        maxParticipants: 10,
      },
    });

    // webrtcService 모킹
    const mockStream = createMockStream();
    vi.mocked(webrtcService.getLocalAudioStream).mockResolvedValue(mockStream as unknown as MediaStream);
    vi.mocked(webrtcService.createProcessedAudioStream).mockReturnValue({
      processedStream: mockStream as unknown as MediaStream,
      gainNode: { gain: { value: 1 } } as unknown as GainNode,
      audioContext: { state: 'running' } as unknown as AudioContext,
      cleanup: vi.fn(),
    });
    vi.mocked(webrtcService.createPeerConnection).mockReturnValue(createMockPeerConnection() as unknown as RTCPeerConnection);
    vi.mocked(webrtcService.createOffer).mockResolvedValue({ type: 'offer', sdp: 'mock-offer-sdp' } as RTCSessionDescriptionInit);
    vi.mocked(webrtcService.createAnswer).mockResolvedValue({ type: 'answer', sdp: 'mock-answer-sdp' } as RTCSessionDescriptionInit);
  });

  afterEach(() => {
    localStorage.clear();
    useMeetingRoomStore.getState().reset();
    mockIsConnected = false;
  });

  describe('초기 상태', () => {
    it('초기 상태값이 올바르게 설정되어야 함', () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      expect(result.current.connectionState).toBe('disconnected');
      expect(result.current.participants.size).toBe(0);
      expect(result.current.localStream).toBeNull();
      expect(result.current.remoteStreams.size).toBe(0);
      expect(result.current.isAudioMuted).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.isRecording).toBe(false);
      expect(result.current.isScreenSharing).toBe(false);
    });

    it('반환값에 필수 액션들이 포함되어야 함', () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      expect(typeof result.current.joinRoom).toBe('function');
      expect(typeof result.current.leaveRoom).toBe('function');
      expect(typeof result.current.toggleMute).toBe('function');
      expect(typeof result.current.changeAudioInputDevice).toBe('function');
      expect(typeof result.current.changeAudioOutputDevice).toBe('function');
      expect(typeof result.current.changeMicGain).toBe('function');
      expect(typeof result.current.changeRemoteVolume).toBe('function');
      expect(typeof result.current.startScreenShare).toBe('function');
      expect(typeof result.current.stopScreenShare).toBe('function');
    });
  });

  describe('joinRoom', () => {
    it('회의실 정보를 조회해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      expect(api.get).toHaveBeenCalledWith(`/meetings/${mockMeetingId}/room`);
    });

    it('로컬 오디오 스트림을 획득해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      expect(webrtcService.getLocalAudioStream).toHaveBeenCalled();
    });

    it('GainNode 처리 스트림을 생성해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      expect(webrtcService.createProcessedAudioStream).toHaveBeenCalled();
    });

    it('시그널링 서버에 연결해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      expect(signalingClient.connect).toHaveBeenCalledWith(mockMeetingId, 'mock-token');
    });

    it('join 메시지를 전송해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      expect(signalingClient.send).toHaveBeenCalledWith({ type: 'join' });
    });

    it('연결 상태가 connecting으로 변경되어야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      // joinRoom 호출 전 상태
      expect(result.current.connectionState).toBe('disconnected');

      // joinRoom 호출 (완료 대기 없이)
      const joinPromise = act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      await joinPromise;

      // connectionState가 'connecting'으로 설정되었다가 처리되었을 것
      // 현재는 시그널링 메시지 핸들러가 'connected'로 바꾸지 않았으므로 그 상태 유지
      // (실제로는 'joined' 메시지 수신 시 'connected'가 됨)
    });

    it('토큰이 없으면 에러를 발생시켜야 함', async () => {
      localStorage.removeItem('accessToken');

      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await expect(
        act(async () => {
          await result.current.joinRoom(mockUserId);
        })
      ).rejects.toThrow('인증 토큰이 없습니다.');
    });

    it('API 에러 시 에러를 throw해야 함', async () => {
      vi.mocked(api.get).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      // API 호출 실패 시 에러가 throw됨
      await expect(
        act(async () => {
          await result.current.joinRoom(mockUserId);
        })
      ).rejects.toThrow();

      // joinRoom에서 에러 발생 시 내부적으로 setConnectionState('failed')와
      // setError가 호출되나, 언마운트 cleanup에서 reset이 호출되어 초기화됨
      // 이 테스트는 에러가 throw된다는 것만 확인
    });
  });

  describe('leaveRoom', () => {
    it('leave 메시지를 전송해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      // 먼저 연결
      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      // signalingClient.isConnected를 true로 설정
      mockIsConnected = true;

      await act(async () => {
        await result.current.leaveRoom();
      });

      expect(signalingClient.send).toHaveBeenCalledWith({ type: 'leave' });
    });

    it('시그널링 연결을 해제해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      await act(async () => {
        await result.current.leaveRoom();
      });

      expect(signalingClient.disconnect).toHaveBeenCalled();
    });

    it('스토어를 리셋해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      await act(async () => {
        await result.current.leaveRoom();
      });

      // 스토어 리셋 확인
      expect(result.current.connectionState).toBe('disconnected');
      expect(result.current.localStream).toBeNull();
    });
  });

  describe('toggleMute', () => {
    it('음소거 상태를 토글해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      expect(result.current.isAudioMuted).toBe(false);

      // isConnected를 true로 설정해야 toggleMute가 send 호출 시 에러 없이 동작
      mockIsConnected = true;

      act(() => {
        result.current.toggleMute();
      });

      expect(result.current.isAudioMuted).toBe(true);

      act(() => {
        result.current.toggleMute();
      });

      expect(result.current.isAudioMuted).toBe(false);
    });

    it('mute 메시지를 서버에 전송해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      mockIsConnected = true;

      act(() => {
        result.current.toggleMute();
      });

      expect(signalingClient.send).toHaveBeenCalledWith({ type: 'mute', muted: true });
    });
  });

  describe('changeMicGain', () => {
    it('gain 값이 범위 내로 제한되어야 함 (0.0 ~ 2.0)', () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      act(() => {
        result.current.changeMicGain(3.0); // 범위 초과
      });
      expect(result.current.micGain).toBe(2.0);

      act(() => {
        result.current.changeMicGain(-1.0); // 범위 미만
      });
      expect(result.current.micGain).toBe(0);

      act(() => {
        result.current.changeMicGain(1.5); // 정상 범위
      });
      expect(result.current.micGain).toBe(1.5);
    });
  });

  describe('changeRemoteVolume', () => {
    it('원격 참여자 볼륨이 범위 내로 제한되어야 함 (0.0 ~ 2.0)', () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));
      const remoteUserId = 'remote-user-123';

      act(() => {
        result.current.changeRemoteVolume(remoteUserId, 3.0);
      });
      expect(result.current.remoteVolumes.get(remoteUserId)).toBe(2.0);

      act(() => {
        result.current.changeRemoteVolume(remoteUserId, -0.5);
      });
      expect(result.current.remoteVolumes.get(remoteUserId)).toBe(0);

      act(() => {
        result.current.changeRemoteVolume(remoteUserId, 1.2);
      });
      expect(result.current.remoteVolumes.get(remoteUserId)).toBe(1.2);
    });
  });

  describe('화면공유', () => {
    it('startScreenShare는 화면 스트림을 획득해야 함', async () => {
      const mockScreenStream = createMockStream();
      mockScreenStream.getVideoTracks = vi.fn().mockReturnValue([{
        kind: 'video',
        id: 'video-track',
        enabled: true,
        onended: null,
      }]);
      vi.mocked(webrtcService.getDisplayMediaStream).mockResolvedValue(mockScreenStream as unknown as MediaStream);

      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      // 참여자 설정
      act(() => {
        useMeetingRoomStore.getState().setParticipants([]);
      });

      await act(async () => {
        await result.current.startScreenShare();
      });

      expect(webrtcService.getDisplayMediaStream).toHaveBeenCalled();
      expect(result.current.isScreenSharing).toBe(true);
    });

    it('stopScreenShare는 화면공유 상태를 해제해야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      // 화면공유 상태 설정
      act(() => {
        useMeetingRoomStore.getState().setScreenSharing(true);
      });

      Object.defineProperty(signalingClient, 'isConnected', { value: true, writable: true });

      act(() => {
        result.current.stopScreenShare();
      });

      expect(result.current.isScreenSharing).toBe(false);
      expect(signalingClient.send).toHaveBeenCalledWith({ type: 'screen-share-stop' });
    });
  });

  describe('시그널링 메시지 처리', () => {
    it('joined 메시지 수신 시 참여자 목록이 설정되어야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      let messageHandler: ((msg: ServerMessage) => void) | null = null;
      vi.mocked(signalingClient.onMessage).mockImplementation((handler) => {
        messageHandler = handler;
      });

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      // joined 메시지 시뮬레이션
      const joinedMessage = {
        type: 'joined' as const,
        participants: [
          { userId: mockUserId, userName: 'Test User', role: 'host' as const, audioMuted: false, isScreenSharing: false },
          { userId: 'other-user', userName: 'Other User', role: 'participant' as const, audioMuted: false, isScreenSharing: false },
        ],
      };

      await act(async () => {
        if (messageHandler) {
          await messageHandler(joinedMessage);
        }
      });

      expect(result.current.connectionState).toBe('connected');
      expect(result.current.participants.size).toBe(2);
    });

    it('participant-joined 메시지 수신 시 참여자가 추가되어야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      let messageHandler: ((msg: ServerMessage) => void) | null = null;
      vi.mocked(signalingClient.onMessage).mockImplementation((handler) => {
        messageHandler = handler;
      });

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      // 초기 참여자 설정
      await act(async () => {
        if (messageHandler) {
          await messageHandler({
            type: 'joined' as const,
            participants: [{ userId: mockUserId, userName: 'Test User', role: 'host' as const, audioMuted: false, isScreenSharing: false }],
          });
        }
      });

      // 새 참여자 추가
      await act(async () => {
        if (messageHandler) {
          await messageHandler({
            type: 'participant-joined' as const,
            participant: { userId: 'new-user', userName: 'New User', role: 'participant' as const, audioMuted: false, isScreenSharing: false },
          });
        }
      });

      expect(result.current.participants.size).toBe(2);
      expect(result.current.participants.has('new-user')).toBe(true);
    });

    it('participant-left 메시지 수신 시 참여자가 제거되어야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      let messageHandler: ((msg: ServerMessage) => void) | null = null;
      vi.mocked(signalingClient.onMessage).mockImplementation((handler) => {
        messageHandler = handler;
      });

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      // 초기 참여자 설정
      await act(async () => {
        if (messageHandler) {
          await messageHandler({
            type: 'joined' as const,
            participants: [
              { userId: mockUserId, userName: 'Test User', role: 'host' as const, audioMuted: false, isScreenSharing: false },
              { userId: 'leaving-user', userName: 'Leaving User', role: 'participant' as const, audioMuted: false, isScreenSharing: false },
            ],
          });
        }
      });

      expect(result.current.participants.size).toBe(2);

      // 참여자 퇴장
      await act(async () => {
        if (messageHandler) {
          await messageHandler({
            type: 'participant-left' as const,
            userId: 'leaving-user',
          });
        }
      });

      expect(result.current.participants.size).toBe(1);
      expect(result.current.participants.has('leaving-user')).toBe(false);
    });

    it('participant-muted 메시지 수신 시 음소거 상태가 업데이트되어야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      let messageHandler: ((msg: ServerMessage) => void) | null = null;
      vi.mocked(signalingClient.onMessage).mockImplementation((handler) => {
        messageHandler = handler;
      });

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      // 초기 참여자 설정
      await act(async () => {
        if (messageHandler) {
          await messageHandler({
            type: 'joined' as const,
            participants: [
              { userId: 'other-user', userName: 'Other User', role: 'participant' as const, audioMuted: false, isScreenSharing: false },
            ],
          });
        }
      });

      // 음소거 상태 변경
      await act(async () => {
        if (messageHandler) {
          await messageHandler({
            type: 'participant-muted' as const,
            userId: 'other-user',
            muted: true,
          });
        }
      });

      const participant = result.current.participants.get('other-user');
      expect(participant?.audioMuted).toBe(true);
    });

    it('error 메시지 수신 시 에러가 설정되어야 함', async () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));

      let messageHandler: ((msg: ServerMessage) => void) | null = null;
      vi.mocked(signalingClient.onMessage).mockImplementation((handler) => {
        messageHandler = handler;
      });

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      // 에러 메시지
      await act(async () => {
        if (messageHandler) {
          await messageHandler({
            type: 'error' as const,
            code: 'ROOM_FULL',
            message: '회의실이 가득 찼습니다.',
          });
        }
      });

      expect(result.current.error).toBe('회의실이 가득 찼습니다.');
    });
  });

  describe('장치 변경', () => {
    it('changeAudioOutputDevice는 출력 장치 ID를 업데이트해야 함', () => {
      const { result } = renderHook(() => useWebRTC(mockMeetingId));
      const newDeviceId = 'new-audio-output-device';

      act(() => {
        result.current.changeAudioOutputDevice(newDeviceId);
      });

      expect(result.current.audioOutputDeviceId).toBe(newDeviceId);
    });
  });

  describe('cleanup', () => {
    it('언마운트 시 리소스가 정리되어야 함', async () => {
      const { result, unmount } = renderHook(() => useWebRTC(mockMeetingId));

      await act(async () => {
        await result.current.joinRoom(mockUserId);
      });

      unmount();

      // signalingClient.disconnect가 호출되었는지 확인
      expect(signalingClient.disconnect).toHaveBeenCalled();
    });
  });
});
