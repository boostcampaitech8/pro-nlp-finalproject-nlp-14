/**
 * WebRTC 훅
 * 시그널링 및 피어 연결 관리
 */

import { useCallback, useEffect, useRef } from 'react';
import { signalingClient } from '@/services/signalingService';
import { webrtcService } from '@/services/webrtcService';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import type { ServerMessage, RoomParticipant } from '@/types/webrtc';
import api from '@/services/api';
import type { MeetingRoomResponse } from '@/types/webrtc';

export function useWebRTC(meetingId: string) {
  const store = useMeetingRoomStore();
  const currentUserIdRef = useRef<string>('');

  /**
   * 회의실 정보 조회
   */
  const fetchRoomInfo = useCallback(async () => {
    try {
      const response = await api.get<MeetingRoomResponse>(`/meetings/${meetingId}/room`);
      store.setMeetingInfo(
        response.data.meetingId,
        response.data.status,
        response.data.iceServers,
        response.data.maxParticipants
      );
      return response.data;
    } catch (error) {
      console.error('[useWebRTC] Failed to fetch room info:', error);
      store.setError('회의실 정보를 불러올 수 없습니다.');
      throw error;
    }
  }, [meetingId, store]);

  /**
   * 새 피어와 연결 생성
   */
  const createPeerConnectionForUser = useCallback(
    (userId: string, isInitiator: boolean) => {
      const { iceServers, localStream } = store;

      const pc = webrtcService.createPeerConnection(
        iceServers,
        // ICE Candidate 콜백
        (candidate) => {
          signalingClient.send({
            type: 'ice-candidate',
            candidate: candidate.toJSON(),
            targetUserId: userId,
          });
        },
        // Track 수신 콜백
        (event) => {
          console.log('[useWebRTC] Track received from:', userId);
          if (event.streams && event.streams[0]) {
            store.addRemoteStream(userId, event.streams[0]);
          }
        },
        // 연결 상태 변경 콜백
        (state) => {
          console.log(`[useWebRTC] Connection state with ${userId}:`, state);
          if (state === 'failed' || state === 'disconnected') {
            // 연결 실패 시 정리
            store.removePeerConnection(userId);
          }
        }
      );

      // 로컬 스트림 추가
      if (localStream) {
        localStream.getTracks().forEach((track) => {
          webrtcService.addTrack(pc, track, localStream);
        });
      }

      store.addPeerConnection(userId, pc);

      // Initiator라면 offer 생성
      if (isInitiator) {
        createAndSendOffer(userId, pc);
      }

      return pc;
    },
    [store]
  );

  /**
   * Offer 생성 및 전송
   */
  const createAndSendOffer = useCallback(async (userId: string, pc: RTCPeerConnection) => {
    try {
      const offer = await webrtcService.createOffer(pc);
      signalingClient.send({
        type: 'offer',
        sdp: offer,
        targetUserId: userId,
      });
    } catch (error) {
      console.error('[useWebRTC] Failed to create offer:', error);
    }
  }, []);

  /**
   * 시그널링 메시지 처리
   */
  const handleSignalingMessage = useCallback(
    async (message: ServerMessage) => {
      switch (message.type) {
        case 'joined': {
          console.log('[useWebRTC] Joined with participants:', message.participants.length);
          store.setParticipants(message.participants);
          store.setConnectionState('connected');

          // 기존 참여자들과 연결 (나를 제외한 모든 참여자에게 offer)
          message.participants.forEach((p: RoomParticipant) => {
            if (p.userId !== currentUserIdRef.current) {
              createPeerConnectionForUser(p.userId, true);
            }
          });
          break;
        }

        case 'participant-joined': {
          console.log('[useWebRTC] Participant joined:', message.participant.userName);
          store.addParticipant(message.participant);
          // 새 참여자가 offer를 보낼 것이므로 기다림
          break;
        }

        case 'participant-left': {
          console.log('[useWebRTC] Participant left:', message.userId);
          store.removeParticipant(message.userId);
          break;
        }

        case 'offer': {
          console.log('[useWebRTC] Received offer from:', message.fromUserId);
          // 이미 연결이 있는지 확인
          let pc = store.getPeerConnection(message.fromUserId);
          if (!pc) {
            pc = createPeerConnectionForUser(message.fromUserId, false);
          }

          try {
            const answer = await webrtcService.createAnswer(pc, message.sdp);
            signalingClient.send({
              type: 'answer',
              sdp: answer,
              targetUserId: message.fromUserId,
            });
          } catch (error) {
            console.error('[useWebRTC] Failed to create answer:', error);
          }
          break;
        }

        case 'answer': {
          console.log('[useWebRTC] Received answer from:', message.fromUserId);
          const pc = store.getPeerConnection(message.fromUserId);
          if (pc) {
            await webrtcService.setRemoteDescription(pc, message.sdp);
          }
          break;
        }

        case 'ice-candidate': {
          const pc = store.getPeerConnection(message.fromUserId);
          if (pc) {
            await webrtcService.addIceCandidate(pc, message.candidate);
          }
          break;
        }

        case 'participant-muted': {
          store.updateParticipantMute(message.userId, message.muted);
          break;
        }

        case 'meeting-ended': {
          console.log('[useWebRTC] Meeting ended:', message.reason);
          store.setConnectionState('disconnected');
          store.setError(message.reason);
          break;
        }

        case 'error': {
          console.error('[useWebRTC] Error:', message.code, message.message);
          store.setError(message.message);
          break;
        }
      }
    },
    [store, createPeerConnectionForUser]
  );

  /**
   * 회의 참여
   */
  const joinRoom = useCallback(
    async (userId: string) => {
      currentUserIdRef.current = userId;
      store.setConnectionState('connecting');

      try {
        // 1. 회의실 정보 조회
        await fetchRoomInfo();

        // 2. 로컬 오디오 스트림 획득
        const localStream = await webrtcService.getLocalAudioStream();
        store.setLocalStream(localStream);

        // 3. 토큰 가져오기
        const token = localStorage.getItem('accessToken');
        if (!token) {
          throw new Error('인증 토큰이 없습니다.');
        }

        // 4. 시그널링 메시지 핸들러 등록
        signalingClient.onMessage(handleSignalingMessage);

        // 5. WebSocket 연결
        await signalingClient.connect(meetingId, token);

        // 6. join 메시지 전송
        signalingClient.send({ type: 'join' });
      } catch (error) {
        console.error('[useWebRTC] Failed to join room:', error);
        store.setConnectionState('failed');
        store.setError(error instanceof Error ? error.message : '회의 참여에 실패했습니다.');
        throw error;
      }
    },
    [meetingId, fetchRoomInfo, handleSignalingMessage, store]
  );

  /**
   * 회의 퇴장
   */
  const leaveRoom = useCallback(() => {
    // leave 메시지 전송
    if (signalingClient.isConnected) {
      signalingClient.send({ type: 'leave' });
    }

    // 연결 해제
    signalingClient.disconnect();

    // 스토어 리셋
    store.reset();
  }, [store]);

  /**
   * 오디오 음소거 토글
   */
  const toggleMute = useCallback(() => {
    const newMuted = !store.isAudioMuted;
    store.setAudioMuted(newMuted);

    // 서버에 상태 전송
    if (signalingClient.isConnected) {
      signalingClient.send({ type: 'mute', muted: newMuted });
    }
  }, [store]);

  /**
   * cleanup
   */
  useEffect(() => {
    return () => {
      leaveRoom();
    };
  }, [leaveRoom]);

  return {
    // 상태
    connectionState: store.connectionState,
    participants: store.participants,
    localStream: store.localStream,
    remoteStreams: store.remoteStreams,
    isAudioMuted: store.isAudioMuted,
    error: store.error,
    meetingStatus: store.meetingStatus,

    // 액션
    joinRoom,
    leaveRoom,
    toggleMute,
  };
}
