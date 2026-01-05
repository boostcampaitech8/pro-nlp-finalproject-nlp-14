/**
 * WebRTC 훅
 * 시그널링 및 피어 연결 관리
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { signalingClient } from '@/services/signalingService';
import { webrtcService } from '@/services/webrtcService';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import type { ServerMessage, RoomParticipant, MeetingRoomResponse } from '@/types/webrtc';
import api from '@/services/api';

export function useWebRTC(meetingId: string) {
  // 개별 상태 selector 사용 (무한 루프 방지)
  const connectionState = useMeetingRoomStore((s) => s.connectionState);
  const participants = useMeetingRoomStore((s) => s.participants);
  const localStream = useMeetingRoomStore((s) => s.localStream);
  const remoteStreams = useMeetingRoomStore((s) => s.remoteStreams);
  const isAudioMuted = useMeetingRoomStore((s) => s.isAudioMuted);
  const error = useMeetingRoomStore((s) => s.error);
  const meetingStatus = useMeetingRoomStore((s) => s.meetingStatus);
  const iceServers = useMeetingRoomStore((s) => s.iceServers);

  // 액션 selector (stable reference)
  const setMeetingInfo = useMeetingRoomStore((s) => s.setMeetingInfo);
  const setConnectionState = useMeetingRoomStore((s) => s.setConnectionState);
  const setError = useMeetingRoomStore((s) => s.setError);
  const setParticipants = useMeetingRoomStore((s) => s.setParticipants);
  const addParticipant = useMeetingRoomStore((s) => s.addParticipant);
  const removeParticipant = useMeetingRoomStore((s) => s.removeParticipant);
  const updateParticipantMute = useMeetingRoomStore((s) => s.updateParticipantMute);
  const setLocalStream = useMeetingRoomStore((s) => s.setLocalStream);
  const setAudioMuted = useMeetingRoomStore((s) => s.setAudioMuted);
  const addRemoteStream = useMeetingRoomStore((s) => s.addRemoteStream);
  const addPeerConnection = useMeetingRoomStore((s) => s.addPeerConnection);
  const removePeerConnection = useMeetingRoomStore((s) => s.removePeerConnection);
  const reset = useMeetingRoomStore((s) => s.reset);

  const currentUserIdRef = useRef<string>('');
  const hasCleanedUpRef = useRef(false);

  // 녹음 관련 상태
  const [isRecording, setIsRecording] = useState(false);
  const recordingPcRef = useRef<RTCPeerConnection | null>(null);

  /**
   * 회의실 정보 조회
   */
  const fetchRoomInfo = useCallback(async () => {
    try {
      const response = await api.get<MeetingRoomResponse>(`/meetings/${meetingId}/room`);
      setMeetingInfo(
        response.data.meetingId,
        response.data.status,
        response.data.iceServers,
        response.data.maxParticipants
      );
      return response.data;
    } catch (err) {
      console.error('[useWebRTC] Failed to fetch room info:', err);
      setError('회의실 정보를 불러올 수 없습니다.');
      throw err;
    }
  }, [meetingId, setMeetingInfo, setError]);

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
    } catch (err) {
      console.error('[useWebRTC] Failed to create offer:', err);
    }
  }, []);

  /**
   * 새 피어와 연결 생성
   */
  const createPeerConnectionForUser = useCallback(
    (userId: string, isInitiator: boolean, currentIceServers: typeof iceServers, currentLocalStream: typeof localStream) => {
      const pc = webrtcService.createPeerConnection(
        currentIceServers,
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
            addRemoteStream(userId, event.streams[0]);
          }
        },
        // 연결 상태 변경 콜백
        (state) => {
          console.log(`[useWebRTC] Connection state with ${userId}:`, state);
          if (state === 'failed' || state === 'disconnected') {
            // 연결 실패 시 정리
            removePeerConnection(userId);
          }
        }
      );

      // 로컬 스트림 추가
      if (currentLocalStream) {
        currentLocalStream.getTracks().forEach((track) => {
          webrtcService.addTrack(pc, track, currentLocalStream);
        });
      }

      addPeerConnection(userId, pc);

      // Initiator라면 offer 생성
      if (isInitiator) {
        createAndSendOffer(userId, pc);
      }

      return pc;
    },
    [addRemoteStream, removePeerConnection, addPeerConnection, createAndSendOffer]
  );

  /**
   * 시그널링 메시지 처리
   */
  const handleSignalingMessage = useCallback(
    async (message: ServerMessage) => {
      // 현재 store 상태 직접 읽기
      const currentState = useMeetingRoomStore.getState();

      switch (message.type) {
        case 'joined': {
          console.log('[useWebRTC] Joined with participants:', message.participants.length);
          setParticipants(message.participants);
          setConnectionState('connected');

          // 기존 참여자들과 연결 (나를 제외한 모든 참여자에게 offer)
          message.participants.forEach((p: RoomParticipant) => {
            if (p.userId !== currentUserIdRef.current) {
              createPeerConnectionForUser(p.userId, true, currentState.iceServers, currentState.localStream);
            }
          });
          break;
        }

        case 'participant-joined': {
          console.log('[useWebRTC] Participant joined:', message.participant.userName);
          addParticipant(message.participant);
          // 새 참여자가 offer를 보낼 것이므로 기다림
          break;
        }

        case 'participant-left': {
          console.log('[useWebRTC] Participant left:', message.userId);
          removeParticipant(message.userId);
          break;
        }

        case 'offer': {
          console.log('[useWebRTC] Received offer from:', message.fromUserId);
          // 이미 연결이 있는지 확인
          let pc = currentState.getPeerConnection(message.fromUserId);
          if (!pc) {
            pc = createPeerConnectionForUser(message.fromUserId, false, currentState.iceServers, currentState.localStream);
          }

          try {
            const answer = await webrtcService.createAnswer(pc, message.sdp);
            signalingClient.send({
              type: 'answer',
              sdp: answer,
              targetUserId: message.fromUserId,
            });
          } catch (err) {
            console.error('[useWebRTC] Failed to create answer:', err);
          }
          break;
        }

        case 'answer': {
          console.log('[useWebRTC] Received answer from:', message.fromUserId);
          const pc = currentState.getPeerConnection(message.fromUserId);
          if (pc) {
            await webrtcService.setRemoteDescription(pc, message.sdp);
          }
          break;
        }

        case 'ice-candidate': {
          const pc = currentState.getPeerConnection(message.fromUserId);
          if (pc) {
            await webrtcService.addIceCandidate(pc, message.candidate);
          }
          break;
        }

        case 'participant-muted': {
          updateParticipantMute(message.userId, message.muted);
          break;
        }

        case 'meeting-ended': {
          console.log('[useWebRTC] Meeting ended:', message.reason);
          setConnectionState('disconnected');
          setError(message.reason);
          break;
        }

        case 'error': {
          console.error('[useWebRTC] Error:', message.code, message.message);
          setError(message.message);
          break;
        }

        // 녹음 관련 메시지
        case 'recording-answer': {
          console.log('[useWebRTC] Received recording answer');
          if (recordingPcRef.current) {
            await webrtcService.setRemoteDescription(recordingPcRef.current, message.sdp);
          }
          break;
        }

        case 'recording-started': {
          console.log('[useWebRTC] Recording started for user:', message.userId);
          if (message.userId === currentUserIdRef.current) {
            setIsRecording(true);
          }
          break;
        }

        case 'recording-stopped': {
          console.log('[useWebRTC] Recording stopped for user:', message.userId);
          if (message.userId === currentUserIdRef.current) {
            setIsRecording(false);
          }
          break;
        }
      }
    },
    [setParticipants, setConnectionState, addParticipant, removeParticipant, updateParticipantMute, setError, createPeerConnectionForUser]
  );

  /**
   * 회의 참여
   */
  const joinRoom = useCallback(
    async (userId: string) => {
      currentUserIdRef.current = userId;
      hasCleanedUpRef.current = false;
      setConnectionState('connecting');

      try {
        // 1. 회의실 정보 조회
        await fetchRoomInfo();

        // 2. 로컬 오디오 스트림 획득
        const stream = await webrtcService.getLocalAudioStream();
        setLocalStream(stream);

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
      } catch (err) {
        console.error('[useWebRTC] Failed to join room:', err);
        setConnectionState('failed');
        setError(err instanceof Error ? err.message : '회의 참여에 실패했습니다.');
        throw err;
      }
    },
    [meetingId, fetchRoomInfo, handleSignalingMessage, setConnectionState, setLocalStream, setError]
  );

  /**
   * 회의 퇴장
   */
  const leaveRoom = useCallback(() => {
    if (hasCleanedUpRef.current) return;
    hasCleanedUpRef.current = true;

    // leave 메시지 전송
    if (signalingClient.isConnected) {
      signalingClient.send({ type: 'leave' });
    }

    // 연결 해제
    signalingClient.disconnect();

    // 스토어 리셋
    reset();
  }, [reset]);

  /**
   * 오디오 음소거 토글
   */
  const toggleMute = useCallback(() => {
    const currentMuted = useMeetingRoomStore.getState().isAudioMuted;
    const newMuted = !currentMuted;
    setAudioMuted(newMuted);

    // 서버에 상태 전송
    if (signalingClient.isConnected) {
      signalingClient.send({ type: 'mute', muted: newMuted });
    }
  }, [setAudioMuted]);

  /**
   * 녹음 시작 - 서버로 오디오를 전송하는 PeerConnection 생성
   */
  const startRecording = useCallback(async () => {
    if (isRecording || recordingPcRef.current) {
      console.log('[useWebRTC] Already recording');
      return;
    }

    const currentState = useMeetingRoomStore.getState();
    if (!currentState.localStream) {
      console.error('[useWebRTC] No local stream for recording');
      return;
    }

    try {
      console.log('[useWebRTC] Starting recording...');

      // 녹음 전용 PeerConnection 생성
      const pc = webrtcService.createPeerConnection(
        currentState.iceServers,
        // ICE Candidate 콜백
        (candidate) => {
          signalingClient.send({
            type: 'recording-ice',
            candidate: candidate.toJSON(),
          });
        },
        // Track 수신 콜백 (녹음에서는 사용 안 함)
        () => {},
        // 연결 상태 변경 콜백
        (state) => {
          console.log('[useWebRTC] Recording connection state:', state);
          if (state === 'failed' || state === 'disconnected') {
            setIsRecording(false);
            recordingPcRef.current = null;
          }
        }
      );

      recordingPcRef.current = pc;

      // 로컬 스트림의 오디오 트랙 추가
      currentState.localStream.getAudioTracks().forEach((track) => {
        pc.addTrack(track, currentState.localStream!);
      });

      // Offer 생성 및 전송
      const offer = await webrtcService.createOffer(pc);
      signalingClient.send({
        type: 'recording-offer',
        sdp: offer,
      });
    } catch (err) {
      console.error('[useWebRTC] Failed to start recording:', err);
      recordingPcRef.current = null;
    }
  }, [isRecording]);

  /**
   * 녹음 중지 - 녹음용 PeerConnection 종료
   */
  const stopRecording = useCallback(() => {
    if (recordingPcRef.current) {
      console.log('[useWebRTC] Stopping recording...');
      recordingPcRef.current.close();
      recordingPcRef.current = null;
      setIsRecording(false);
    }
  }, []);

  /**
   * cleanup - 빈 의존성 배열로 마운트/언마운트 시에만 실행
   */
  useEffect(() => {
    return () => {
      // 녹음 정리
      if (recordingPcRef.current) {
        recordingPcRef.current.close();
        recordingPcRef.current = null;
      }

      // 직접 store 접근하여 cleanup
      if (!hasCleanedUpRef.current) {
        hasCleanedUpRef.current = true;

        if (signalingClient.isConnected) {
          signalingClient.send({ type: 'leave' });
        }
        signalingClient.disconnect();
        useMeetingRoomStore.getState().reset();
      }
    };
  }, []);

  return {
    // 상태
    connectionState,
    participants,
    localStream,
    remoteStreams,
    isAudioMuted,
    error,
    meetingStatus,
    isRecording,

    // 액션
    joinRoom,
    leaveRoom,
    toggleMute,
    startRecording,
    stopRecording,
  };
}
