/**
 * 화면공유 훅
 * 화면공유 스트림 및 피어 연결 관리 담당
 */

import { useCallback, useRef } from 'react';
import { webrtcService } from '@/services/webrtcService';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import type { ClientMessage, IceServer, RoomParticipant } from '@/types/webrtc';
import logger from '@/utils/logger';

interface UseScreenShareOptions {
  currentUserId: string;
  onSendMessage: (message: ClientMessage) => void;
  onIceCandidate: (userId: string, candidate: RTCIceCandidate) => void;
}

interface UseScreenShareReturn {
  // 상태
  isScreenSharing: boolean;
  screenStream: MediaStream | null;
  remoteScreenStreams: Map<string, MediaStream>;

  // 액션
  startScreenShare: (
    iceServers: IceServer[],
    participants: Map<string, RoomParticipant>
  ) => Promise<void>;
  stopScreenShare: () => void;

  // 화면공유 피어 연결 관리
  createScreenPeerConnection: (userId: string, iceServers: IceServer[]) => RTCPeerConnection;
  createScreenAnswer: (userId: string, remoteSdp: RTCSessionDescriptionInit) => Promise<RTCSessionDescriptionInit>;
  setScreenRemoteDescription: (userId: string, sdp: RTCSessionDescriptionInit) => Promise<void>;
  addScreenIceCandidate: (userId: string, candidate: RTCIceCandidateInit) => Promise<void>;
}

export function useScreenShare({
  currentUserId,
  onSendMessage,
  onIceCandidate,
}: UseScreenShareOptions): UseScreenShareReturn {
  // 화면공유 피어 연결 Map
  const screenPeerConnectionsRef = useRef<Map<string, RTCPeerConnection>>(new Map());

  // Store 상태
  const isScreenSharing = useMeetingRoomStore((s) => s.isScreenSharing);
  const screenStream = useMeetingRoomStore((s) => s.screenStream);
  const remoteScreenStreams = useMeetingRoomStore((s) => s.remoteScreenStreams);

  // Store 액션
  const setScreenSharing = useMeetingRoomStore((s) => s.setScreenSharing);
  const setScreenStream = useMeetingRoomStore((s) => s.setScreenStream);
  const addRemoteScreenStream = useMeetingRoomStore((s) => s.addRemoteScreenStream);
  const removeRemoteScreenStream = useMeetingRoomStore((s) => s.removeRemoteScreenStream);
  const addScreenPeerConnection = useMeetingRoomStore((s) => s.addScreenPeerConnection);
  const removeScreenPeerConnection = useMeetingRoomStore((s) => s.removeScreenPeerConnection);

  /**
   * 화면공유 시작
   */
  const startScreenShare = useCallback(async (
    iceServers: IceServer[],
    participants: Map<string, RoomParticipant>
  ): Promise<void> => {
    if (isScreenSharing) {
      logger.log('[useScreenShare] Already sharing screen');
      return;
    }

    try {
      // 1. 화면공유 스트림 획득
      const stream = await webrtcService.getDisplayMediaStream();
      setScreenStream(stream);
      setScreenSharing(true);

      // 화면공유 중지 이벤트 리스너
      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.onended = () => {
          logger.log('[useScreenShare] Screen share track ended by user');
          stopScreenShare();
        };
      }

      // 2. 서버에 화면공유 시작 알림
      onSendMessage({ type: 'screen-share-start' });

      // 3. 모든 참여자에게 화면공유 피어 연결 생성 및 offer 전송
      participants.forEach((participant) => {
        if (participant.userId !== currentUserId) {
          // 화면공유용 피어 연결 생성
          const pc = webrtcService.createPeerConnection(
            iceServers,
            (candidate) => {
              onIceCandidate(participant.userId, candidate);
            },
            () => {},
            (state) => {
              logger.log(`[useScreenShare] Screen connection state with ${participant.userId}:`, state);
            }
          );

          // 비디오 트랙 추가
          stream.getTracks().forEach((track) => {
            webrtcService.addTrack(pc, track, stream);
          });

          screenPeerConnectionsRef.current.set(participant.userId, pc);
          addScreenPeerConnection(participant.userId, pc);

          // Offer 생성 및 전송
          webrtcService.createOffer(pc).then((offer) => {
            onSendMessage({
              type: 'screen-offer',
              sdp: offer,
              targetUserId: participant.userId,
            });
          }).catch((err) => {
            logger.error(`[useScreenShare] Failed to create screen offer for ${participant.userId}:`, err);
          });
        }
      });

      logger.log('[useScreenShare] Screen sharing started');
    } catch (err) {
      logger.error('[useScreenShare] Failed to start screen share:', err);
      setScreenSharing(false);
      setScreenStream(null);
      throw err;
    }
  }, [isScreenSharing, currentUserId, onSendMessage, onIceCandidate, setScreenSharing, setScreenStream, addScreenPeerConnection]);

  /**
   * 화면공유 중지
   */
  const stopScreenShare = useCallback(() => {
    if (!isScreenSharing) {
      logger.log('[useScreenShare] Not sharing screen');
      return;
    }

    // 1. 서버에 화면공유 중지 알림
    onSendMessage({ type: 'screen-share-stop' });

    // 2. 화면공유 피어 연결 정리
    screenPeerConnectionsRef.current.forEach((pc, userId) => {
      pc.close();
      removeScreenPeerConnection(userId);
    });
    screenPeerConnectionsRef.current.clear();

    // 3. 스트림 정리
    setScreenStream(null);
    setScreenSharing(false);

    logger.log('[useScreenShare] Screen sharing stopped');
  }, [isScreenSharing, onSendMessage, setScreenStream, setScreenSharing, removeScreenPeerConnection]);

  /**
   * 화면공유 수신용 피어 연결 생성
   */
  const createScreenPeerConnection = useCallback((
    userId: string,
    iceServers: IceServer[]
  ): RTCPeerConnection => {
    const pc = webrtcService.createPeerConnection(
      iceServers,
      (candidate) => {
        onSendMessage({
          type: 'screen-ice-candidate',
          candidate: candidate.toJSON(),
          targetUserId: userId,
        });
      },
      (event) => {
        logger.log('[useScreenShare] Screen track received from:', userId);
        if (event.streams && event.streams[0]) {
          addRemoteScreenStream(userId, event.streams[0]);
        }
      },
      (state) => {
        logger.log(`[useScreenShare] Screen connection state with ${userId}:`, state);
        if (state === 'failed' || state === 'disconnected') {
          removeScreenPeerConnection(userId);
          removeRemoteScreenStream(userId);
        }
      }
    );

    screenPeerConnectionsRef.current.set(userId, pc);
    addScreenPeerConnection(userId, pc);
    return pc;
  }, [onSendMessage, addRemoteScreenStream, removeRemoteScreenStream, addScreenPeerConnection, removeScreenPeerConnection]);

  /**
   * 화면공유 Answer 생성
   */
  const createScreenAnswer = useCallback(async (
    userId: string,
    remoteSdp: RTCSessionDescriptionInit
  ): Promise<RTCSessionDescriptionInit> => {
    const pc = screenPeerConnectionsRef.current.get(userId);
    if (!pc) {
      throw new Error(`No screen peer connection for user: ${userId}`);
    }
    return webrtcService.createAnswer(pc, remoteSdp);
  }, []);

  /**
   * 화면공유 Remote Description 설정
   */
  const setScreenRemoteDescription = useCallback(async (
    userId: string,
    sdp: RTCSessionDescriptionInit
  ): Promise<void> => {
    const pc = screenPeerConnectionsRef.current.get(userId);
    if (pc) {
      await webrtcService.setRemoteDescription(pc, sdp);
    }
  }, []);

  /**
   * 화면공유 ICE Candidate 추가
   */
  const addScreenIceCandidate = useCallback(async (
    userId: string,
    candidate: RTCIceCandidateInit
  ): Promise<void> => {
    const pc = screenPeerConnectionsRef.current.get(userId);
    if (pc) {
      await webrtcService.addIceCandidate(pc, candidate);
    }
  }, []);

  return {
    isScreenSharing,
    screenStream,
    remoteScreenStreams,
    startScreenShare,
    stopScreenShare,
    createScreenPeerConnection,
    createScreenAnswer,
    setScreenRemoteDescription,
    addScreenIceCandidate,
  };
}
