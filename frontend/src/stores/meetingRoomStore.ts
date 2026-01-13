/**
 * 회의실 상태 관리 스토어
 */

import { create } from 'zustand';
import type { ConnectionState, IceServer, RoomParticipant } from '@/types/webrtc';
import type { ChatMessage } from '@/types/chat';
import {
  loadAudioSettings,
  saveAudioSettings,
  loadRemoteVolumes,
  saveRemoteVolumes,
} from '@/utils/audioSettingsStorage';

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

  // 화면공유
  isScreenSharing: boolean;
  screenStream: MediaStream | null;
  remoteScreenStreams: Map<string, MediaStream>; // userId -> screen stream
  screenPeerConnections: Map<string, RTCPeerConnection>; // userId -> screen PC

  // 채팅
  chatMessages: ChatMessage[];

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

  // 화면공유 Actions
  setScreenSharing: (isSharing: boolean) => void;
  setScreenStream: (stream: MediaStream | null) => void;
  addRemoteScreenStream: (userId: string, stream: MediaStream) => void;
  removeRemoteScreenStream: (userId: string) => void;
  addScreenPeerConnection: (userId: string, pc: RTCPeerConnection) => void;
  removeScreenPeerConnection: (userId: string) => void;
  getScreenPeerConnection: (userId: string) => RTCPeerConnection | undefined;
  updateParticipantScreenSharing: (userId: string, isSharing: boolean) => void;

  // 채팅 Actions
  addChatMessage: (message: ChatMessage) => void;
  setChatMessages: (messages: ChatMessage[]) => void;
  clearChatMessages: () => void;

  reset: () => void;
}

// 캐시된 설정 불러오기
const cachedAudioSettings = loadAudioSettings();
const cachedRemoteVolumes = loadRemoteVolumes();

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
  // 캐시된 오디오 설정 적용
  audioInputDeviceId: cachedAudioSettings.audioInputDeviceId ?? null,
  audioOutputDeviceId: cachedAudioSettings.audioOutputDeviceId ?? null,
  micGain: cachedAudioSettings.micGain ?? 1.0,
  remoteStreams: new Map<string, MediaStream>(),
  // 캐시된 볼륨 설정 적용
  remoteVolumes: cachedRemoteVolumes,
  peerConnections: new Map<string, RTCPeerConnection>(),
  // 화면공유
  isScreenSharing: false,
  screenStream: null,
  remoteScreenStreams: new Map<string, MediaStream>(),
  screenPeerConnections: new Map<string, RTCPeerConnection>(),
  // 채팅
  chatMessages: [] as ChatMessage[],
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
    // localStorage에 저장
    const { micGain, audioOutputDeviceId } = get();
    saveAudioSettings({ micGain, audioInputDeviceId, audioOutputDeviceId });
  },

  setAudioOutputDeviceId: (audioOutputDeviceId) => {
    set({ audioOutputDeviceId });
    // localStorage에 저장
    const { micGain, audioInputDeviceId } = get();
    saveAudioSettings({ micGain, audioInputDeviceId, audioOutputDeviceId });
  },

  setMicGain: (micGain) => {
    set({ micGain });
    // localStorage에 저장
    const { audioInputDeviceId, audioOutputDeviceId } = get();
    saveAudioSettings({ micGain, audioInputDeviceId, audioOutputDeviceId });
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
    // 볼륨 설정은 캐시되어야 하므로 삭제하지 않음
  },

  setRemoteVolume: (userId, volume) => {
    const remoteVolumes = new Map(get().remoteVolumes);
    remoteVolumes.set(userId, volume);
    set({ remoteVolumes });
    // localStorage에 저장
    saveRemoteVolumes(remoteVolumes);
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

  // 화면공유 Actions
  setScreenSharing: (isScreenSharing) => {
    set({ isScreenSharing });
  },

  setScreenStream: (screenStream) => {
    // 기존 스트림 정리
    const oldStream = get().screenStream;
    if (oldStream) {
      oldStream.getTracks().forEach((track) => track.stop());
    }
    set({ screenStream });
  },

  addRemoteScreenStream: (userId, stream) => {
    const remoteScreenStreams = new Map(get().remoteScreenStreams);
    remoteScreenStreams.set(userId, stream);
    set({ remoteScreenStreams });
  },

  removeRemoteScreenStream: (userId) => {
    const remoteScreenStreams = new Map(get().remoteScreenStreams);
    const stream = remoteScreenStreams.get(userId);
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      remoteScreenStreams.delete(userId);
      set({ remoteScreenStreams });
    }
  },

  addScreenPeerConnection: (userId, pc) => {
    const screenPeerConnections = new Map(get().screenPeerConnections);
    screenPeerConnections.set(userId, pc);
    set({ screenPeerConnections });
  },

  removeScreenPeerConnection: (userId) => {
    const screenPeerConnections = new Map(get().screenPeerConnections);
    const pc = screenPeerConnections.get(userId);
    if (pc) {
      pc.close();
      screenPeerConnections.delete(userId);
      set({ screenPeerConnections });
    }
  },

  getScreenPeerConnection: (userId) => {
    return get().screenPeerConnections.get(userId);
  },

  updateParticipantScreenSharing: (userId, isSharing) => {
    const participants = new Map(get().participants);
    const participant = participants.get(userId);
    if (participant) {
      participants.set(userId, { ...participant, isScreenSharing: isSharing });
      set({ participants });
    }
  },

  // 채팅 Actions
  addChatMessage: (message) => {
    const chatMessages = [...get().chatMessages, message];
    set({ chatMessages });
  },

  setChatMessages: (chatMessages) => {
    set({ chatMessages });
  },

  clearChatMessages: () => {
    set({ chatMessages: [] });
  },

  reset: () => {
    // 모든 리소스 정리
    const {
      localStream,
      remoteStreams,
      peerConnections,
      screenStream,
      remoteScreenStreams,
      screenPeerConnections,
      // 캐시된 설정 유지
      audioInputDeviceId,
      audioOutputDeviceId,
      micGain,
      remoteVolumes,
    } = get();

    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
    }

    if (screenStream) {
      screenStream.getTracks().forEach((track) => track.stop());
    }

    remoteStreams.forEach((stream) => {
      stream.getTracks().forEach((track) => track.stop());
    });

    remoteScreenStreams.forEach((stream) => {
      stream.getTracks().forEach((track) => track.stop());
    });

    peerConnections.forEach((pc) => {
      pc.close();
    });

    screenPeerConnections.forEach((pc) => {
      pc.close();
    });

    // 캐시된 설정은 유지하면서 초기화
    set({
      ...initialState,
      audioInputDeviceId,
      audioOutputDeviceId,
      micGain,
      remoteVolumes,
    });
  },
}));
