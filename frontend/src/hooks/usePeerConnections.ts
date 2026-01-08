/**
 * 피어 연결 관리 훅
 * WebRTC RTCPeerConnection 생성 및 관리 담당
 */

import { useCallback, useRef } from 'react';
import { webrtcService, type ProcessedAudioStream } from '@/services/webrtcService';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import type { IceServer } from '@/types/webrtc';

interface UsePeerConnectionsOptions {
  onIceCandidate: (userId: string, candidate: RTCIceCandidate) => void;
  onTrack: (userId: string, stream: MediaStream) => void;
  onConnectionStateChange: (userId: string, state: RTCPeerConnectionState) => void;
}

interface UsePeerConnectionsReturn {
  // 로컬 스트림
  initLocalStream: (micGain: number, deviceId?: string) => Promise<MediaStream>;
  cleanupLocalStream: () => void;

  // 피어 연결
  createPeerConnection: (
    userId: string,
    iceServers: IceServer[],
    localStream: MediaStream | null,
    isInitiator: boolean
  ) => RTCPeerConnection;
  closePeerConnection: (userId: string) => void;
  closeAllPeerConnections: () => void;

  // Offer/Answer
  createOffer: (userId: string) => Promise<RTCSessionDescriptionInit>;
  createAnswer: (userId: string, remoteSdp: RTCSessionDescriptionInit) => Promise<RTCSessionDescriptionInit>;
  setRemoteDescription: (userId: string, sdp: RTCSessionDescriptionInit) => Promise<void>;
  addIceCandidate: (userId: string, candidate: RTCIceCandidateInit) => Promise<void>;

  // 트랙 교체
  replaceTrack: (userId: string, newTrack: MediaStreamTrack) => Promise<void>;

  // 마이크 gain
  changeMicGain: (gain: number) => void;
}

export function usePeerConnections({
  onIceCandidate,
  onTrack,
  onConnectionStateChange,
}: UsePeerConnectionsOptions): UsePeerConnectionsReturn {
  // 피어 연결 Map (store와 별도로 관리)
  const peerConnectionsRef = useRef<Map<string, RTCPeerConnection>>(new Map());

  // GainNode 처리 관련 ref
  const processedAudioRef = useRef<ProcessedAudioStream | null>(null);
  const rawStreamRef = useRef<MediaStream | null>(null);

  // Store 액션
  const addPeerConnection = useMeetingRoomStore((s) => s.addPeerConnection);
  const removePeerConnection = useMeetingRoomStore((s) => s.removePeerConnection);
  const addRemoteStream = useMeetingRoomStore((s) => s.addRemoteStream);
  const removeRemoteStream = useMeetingRoomStore((s) => s.removeRemoteStream);

  /**
   * 로컬 오디오 스트림 초기화 (GainNode 적용)
   */
  const initLocalStream = useCallback(async (micGain: number, deviceId?: string): Promise<MediaStream> => {
    // 기존 스트림 정리
    if (rawStreamRef.current) {
      rawStreamRef.current.getTracks().forEach((track) => track.stop());
    }
    if (processedAudioRef.current) {
      processedAudioRef.current.cleanup();
    }

    // 새 스트림 획득
    const rawStream = await webrtcService.getLocalAudioStream(deviceId);
    rawStreamRef.current = rawStream;

    // GainNode를 통해 처리된 스트림 생성
    const processed = webrtcService.createProcessedAudioStream(rawStream, micGain);
    processedAudioRef.current = processed;

    return processed.processedStream;
  }, []);

  /**
   * 로컬 스트림 정리
   */
  const cleanupLocalStream = useCallback(() => {
    if (processedAudioRef.current) {
      processedAudioRef.current.cleanup();
      processedAudioRef.current = null;
    }
    if (rawStreamRef.current) {
      rawStreamRef.current.getTracks().forEach((track) => track.stop());
      rawStreamRef.current = null;
    }
  }, []);

  /**
   * 피어 연결 생성
   */
  const createPeerConnection = useCallback(
    (
      userId: string,
      iceServers: IceServer[],
      localStream: MediaStream | null,
      _isInitiator: boolean
    ): RTCPeerConnection => {
      const pc = webrtcService.createPeerConnection(
        iceServers,
        // ICE Candidate 콜백
        (candidate) => {
          onIceCandidate(userId, candidate);
        },
        // Track 수신 콜백
        (event) => {
          if (event.streams && event.streams[0]) {
            addRemoteStream(userId, event.streams[0]);
            onTrack(userId, event.streams[0]);
          }
        },
        // 연결 상태 변경 콜백
        (state) => {
          onConnectionStateChange(userId, state);
          if (state === 'failed' || state === 'disconnected') {
            removePeerConnection(userId);
            removeRemoteStream(userId);
          }
        }
      );

      // 로컬 스트림 추가
      if (localStream) {
        localStream.getTracks().forEach((track) => {
          webrtcService.addTrack(pc, track, localStream);
        });
      }

      // 저장
      peerConnectionsRef.current.set(userId, pc);
      addPeerConnection(userId, pc);

      return pc;
    },
    [onIceCandidate, onTrack, onConnectionStateChange, addRemoteStream, removeRemoteStream, addPeerConnection, removePeerConnection]
  );

  /**
   * 피어 연결 종료
   */
  const closePeerConnection = useCallback((userId: string) => {
    const pc = peerConnectionsRef.current.get(userId);
    if (pc) {
      pc.close();
      peerConnectionsRef.current.delete(userId);
      removePeerConnection(userId);
      removeRemoteStream(userId);
    }
  }, [removePeerConnection, removeRemoteStream]);

  /**
   * 모든 피어 연결 종료
   */
  const closeAllPeerConnections = useCallback(() => {
    peerConnectionsRef.current.forEach((pc, userId) => {
      pc.close();
      removePeerConnection(userId);
      removeRemoteStream(userId);
    });
    peerConnectionsRef.current.clear();
  }, [removePeerConnection, removeRemoteStream]);

  /**
   * Offer 생성
   */
  const createOffer = useCallback(async (userId: string): Promise<RTCSessionDescriptionInit> => {
    const pc = peerConnectionsRef.current.get(userId);
    if (!pc) {
      throw new Error(`No peer connection for user: ${userId}`);
    }
    return webrtcService.createOffer(pc);
  }, []);

  /**
   * Answer 생성
   */
  const createAnswer = useCallback(async (
    userId: string,
    remoteSdp: RTCSessionDescriptionInit
  ): Promise<RTCSessionDescriptionInit> => {
    const pc = peerConnectionsRef.current.get(userId);
    if (!pc) {
      throw new Error(`No peer connection for user: ${userId}`);
    }
    return webrtcService.createAnswer(pc, remoteSdp);
  }, []);

  /**
   * Remote Description 설정
   */
  const setRemoteDescription = useCallback(async (
    userId: string,
    sdp: RTCSessionDescriptionInit
  ): Promise<void> => {
    const pc = peerConnectionsRef.current.get(userId);
    if (!pc) {
      throw new Error(`No peer connection for user: ${userId}`);
    }
    await webrtcService.setRemoteDescription(pc, sdp);
  }, []);

  /**
   * ICE Candidate 추가
   */
  const addIceCandidate = useCallback(async (
    userId: string,
    candidate: RTCIceCandidateInit
  ): Promise<void> => {
    const pc = peerConnectionsRef.current.get(userId);
    if (pc) {
      await webrtcService.addIceCandidate(pc, candidate);
    }
  }, []);

  /**
   * 트랙 교체 (장치 변경 시)
   */
  const replaceTrack = useCallback(async (
    userId: string,
    newTrack: MediaStreamTrack
  ): Promise<void> => {
    const pc = peerConnectionsRef.current.get(userId);
    if (!pc) return;

    const senders = pc.getSenders();
    const audioSender = senders.find((s) => s.track?.kind === 'audio');
    if (audioSender) {
      await audioSender.replaceTrack(newTrack);
    }
  }, []);

  /**
   * 마이크 gain 변경
   */
  const changeMicGain = useCallback((gain: number) => {
    // gain 값 범위 제한 (0.0 ~ 2.0)
    const clampedGain = Math.max(0, Math.min(2, gain));

    if (processedAudioRef.current) {
      processedAudioRef.current.gainNode.gain.value = clampedGain;
    }
  }, []);

  return {
    initLocalStream,
    cleanupLocalStream,
    createPeerConnection,
    closePeerConnection,
    closeAllPeerConnections,
    createOffer,
    createAnswer,
    setRemoteDescription,
    addIceCandidate,
    replaceTrack,
    changeMicGain,
  };
}
