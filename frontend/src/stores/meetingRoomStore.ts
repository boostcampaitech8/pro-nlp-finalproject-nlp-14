/**
 * 회의실 상태 관리 스토어
 */

import { create } from 'zustand';
import type { ConnectionState, IceServer, RoomParticipant } from '@/types/webrtc';

interface MeetingRoomState {
  // 회의 정보
  meetingId: string | null;
  meetingStatus: string | null;
  maxParticipants: number;
  iceServers: IceServer[];

  // 연결 상태
  connectionState: ConnectionState;
  error: string | null;

  // 참여자
  participants: Map<string, RoomParticipant>;

  // 로컬 미디어
  localStream: MediaStream | null;
  isAudioMuted: boolean;

  // 장치 선택
  audioInputDeviceId: string | null;
  audioOutputDeviceId: string | null;

  // 마이크 gain (1.0 = 100%, 0.0 ~ 2.0 범위, 20% 단위)
  micGain: number;

  // 원격 스트림
  remoteStreams: Map<string, MediaStream>;

  // 원격 참여자별 볼륨 (userId -> volume, 0.0 ~ 2.0)
  remoteVolumes: Map<string, number>;

  // 피어 연결
  peerConnections: Map<string, RTCPeerConnection>;

  // Actions
  setMeetingInfo: (meetingId: string, status: string, iceServers: IceServer[], maxParticipants: number) => void;
  setConnectionState: (state: ConnectionState) => void;
  setError: (error: string | null) => void;

  setParticipants: (participants: RoomParticipant[]) => void;
  addParticipant: (participant: RoomParticipant) => void;
  removeParticipant: (userId: string) => void;
  updateParticipantMute: (userId: string, muted: boolean) => void;

  setLocalStream: (stream: MediaStream | null) => void;
  setAudioMuted: (muted: boolean) => void;

  setAudioInputDeviceId: (deviceId: string | null) => void;
  setAudioOutputDeviceId: (deviceId: string | null) => void;
  setMicGain: (gain: number) => void;

  addRemoteStream: (userId: string, stream: MediaStream) => void;
  removeRemoteStream: (userId: string) => void;
  setRemoteVolume: (userId: string, volume: number) => void;

  addPeerConnection: (userId: string, pc: RTCPeerConnection) => void;
  removePeerConnection: (userId: string) => void;
  getPeerConnection: (userId: string) => RTCPeerConnection | undefined;

  reset: () => void;
}

const initialState = {
  meetingId: null,
  meetingStatus: null,
  maxParticipants: 10,
  iceServers: [],
  connectionState: 'disconnected' as ConnectionState,
  error: null,
  participants: new Map<string, RoomParticipant>(),
  localStream: null,
  isAudioMuted: false,
  audioInputDeviceId: null,
  audioOutputDeviceId: null,
  micGain: 1.0,
  remoteStreams: new Map<string, MediaStream>(),
  remoteVolumes: new Map<string, number>(),
  peerConnections: new Map<string, RTCPeerConnection>(),
};

export const useMeetingRoomStore = create<MeetingRoomState>((set, get) => ({
  ...initialState,

  setMeetingInfo: (meetingId, status, iceServers, maxParticipants) => {
    set({ meetingId, meetingStatus: status, iceServers, maxParticipants });
  },

  setConnectionState: (connectionState) => {
    set({ connectionState });
  },

  setError: (error) => {
    set({ error });
  },

  setParticipants: (participantsList) => {
    const participants = new Map<string, RoomParticipant>();
    participantsList.forEach((p) => {
      participants.set(p.userId, p);
    });
    set({ participants });
  },

  addParticipant: (participant) => {
    const participants = new Map(get().participants);
    participants.set(participant.userId, participant);
    set({ participants });
  },

  removeParticipant: (userId) => {
    const participants = new Map(get().participants);
    participants.delete(userId);
    set({ participants });

    // 관련 스트림도 제거
    get().removeRemoteStream(userId);
    get().removePeerConnection(userId);
  },

  updateParticipantMute: (userId, muted) => {
    const participants = new Map(get().participants);
    const participant = participants.get(userId);
    if (participant) {
      participants.set(userId, { ...participant, audioMuted: muted });
      set({ participants });
    }
  },

  setLocalStream: (stream) => {
    set({ localStream: stream });
  },

  setAudioMuted: (isAudioMuted) => {
    set({ isAudioMuted });
    // 로컬 스트림 트랙 음소거
    const { localStream } = get();
    if (localStream) {
      localStream.getAudioTracks().forEach((track) => {
        track.enabled = !isAudioMuted;
      });
    }
  },

  setAudioInputDeviceId: (audioInputDeviceId) => {
    set({ audioInputDeviceId });
  },

  setAudioOutputDeviceId: (audioOutputDeviceId) => {
    set({ audioOutputDeviceId });
  },

  setMicGain: (micGain) => {
    set({ micGain });
  },

  addRemoteStream: (userId, stream) => {
    const remoteStreams = new Map(get().remoteStreams);
    remoteStreams.set(userId, stream);
    set({ remoteStreams });
  },

  removeRemoteStream: (userId) => {
    const remoteStreams = new Map(get().remoteStreams);
    const stream = remoteStreams.get(userId);
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      remoteStreams.delete(userId);
      set({ remoteStreams });
    }

    // 볼륨 설정도 함께 제거
    const remoteVolumes = new Map(get().remoteVolumes);
    remoteVolumes.delete(userId);
    set({ remoteVolumes });
  },

  setRemoteVolume: (userId, volume) => {
    const remoteVolumes = new Map(get().remoteVolumes);
    remoteVolumes.set(userId, volume);
    set({ remoteVolumes });
  },

  addPeerConnection: (userId, pc) => {
    const peerConnections = new Map(get().peerConnections);
    peerConnections.set(userId, pc);
    set({ peerConnections });
  },

  removePeerConnection: (userId) => {
    const peerConnections = new Map(get().peerConnections);
    const pc = peerConnections.get(userId);
    if (pc) {
      pc.close();
      peerConnections.delete(userId);
      set({ peerConnections });
    }
  },

  getPeerConnection: (userId) => {
    return get().peerConnections.get(userId);
  },

  reset: () => {
    // 모든 리소스 정리
    const { localStream, remoteStreams, peerConnections } = get();

    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
    }

    remoteStreams.forEach((stream) => {
      stream.getTracks().forEach((track) => track.stop());
    });

    peerConnections.forEach((pc) => {
      pc.close();
    });

    set(initialState);
  },
}));
