/**
 * WebRTC 훅 (리팩토링 버전)
 * useSignaling, usePeerConnections, useRecording, useScreenShare를 조합
 * 기존 API와 동일한 인터페이스 유지
 */

import { useCallback, useEffect, useRef } from 'react';
import api, { ensureValidToken } from '@/services/api';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import type { ServerMessage, RoomParticipant, MeetingRoomResponse } from '@/types/webrtc';
import logger from '@/utils/logger';

import { useSignaling } from './useSignaling';
import { usePeerConnections } from './usePeerConnections';
import { useRecording } from './useRecording';
import { useScreenShare } from './useScreenShare';

// 토큰 갱신 주기 (15분)
const TOKEN_REFRESH_INTERVAL = 15 * 60 * 1000;

export function useWebRTC(meetingId: string) {
  // Store 상태 selector
  const connectionState = useMeetingRoomStore((s) => s.connectionState);
  const participants = useMeetingRoomStore((s) => s.participants);
  const localStream = useMeetingRoomStore((s) => s.localStream);
  const remoteStreams = useMeetingRoomStore((s) => s.remoteStreams);
  const isAudioMuted = useMeetingRoomStore((s) => s.isAudioMuted);
  const error = useMeetingRoomStore((s) => s.error);
  const meetingStatus = useMeetingRoomStore((s) => s.meetingStatus);
  const audioInputDeviceId = useMeetingRoomStore((s) => s.audioInputDeviceId);
  const audioOutputDeviceId = useMeetingRoomStore((s) => s.audioOutputDeviceId);
  const micGain = useMeetingRoomStore((s) => s.micGain);
  const remoteVolumes = useMeetingRoomStore((s) => s.remoteVolumes);

  // Store 액션 selector
  const setMeetingInfo = useMeetingRoomStore((s) => s.setMeetingInfo);
  const setConnectionState = useMeetingRoomStore((s) => s.setConnectionState);
  const setError = useMeetingRoomStore((s) => s.setError);
  const setParticipants = useMeetingRoomStore((s) => s.setParticipants);
  const addParticipant = useMeetingRoomStore((s) => s.addParticipant);
  const removeParticipant = useMeetingRoomStore((s) => s.removeParticipant);
  const updateParticipantMute = useMeetingRoomStore((s) => s.updateParticipantMute);
  const setLocalStream = useMeetingRoomStore((s) => s.setLocalStream);
  const setAudioMuted = useMeetingRoomStore((s) => s.setAudioMuted);
  const setAudioInputDeviceId = useMeetingRoomStore((s) => s.setAudioInputDeviceId);
  const setAudioOutputDeviceId = useMeetingRoomStore((s) => s.setAudioOutputDeviceId);
  const setMicGain = useMeetingRoomStore((s) => s.setMicGain);
  const setRemoteVolume = useMeetingRoomStore((s) => s.setRemoteVolume);
  const updateParticipantScreenSharing = useMeetingRoomStore((s) => s.updateParticipantScreenSharing);
  const removeRemoteScreenStream = useMeetingRoomStore((s) => s.removeRemoteScreenStream);
  const removeScreenPeerConnection = useMeetingRoomStore((s) => s.removeScreenPeerConnection);
  const chatMessages = useMeetingRoomStore((s) => s.chatMessages);
  const addChatMessage = useMeetingRoomStore((s) => s.addChatMessage);
  const setChatMessages = useMeetingRoomStore((s) => s.setChatMessages);
  const reset = useMeetingRoomStore((s) => s.reset);

  // Refs
  const currentUserIdRef = useRef<string>('');
  const hasCleanedUpRef = useRef(false);
  const stopRecordingRef = useRef<() => Promise<void>>();
  const startRecordingRef = useRef<() => void>();
  const hasStartedRecordingRef = useRef(false);

  /**
   * 시그널링 메시지 핸들러
   */
  const handleSignalingMessage = useCallback(
    async (message: ServerMessage) => {
      const currentState = useMeetingRoomStore.getState();

      switch (message.type) {
        case 'joined': {
          logger.log('[useWebRTC] Joined with participants:', message.participants.length);
          setParticipants(message.participants);
          setConnectionState('connected');

          // 기존 참여자들과 연결
          message.participants.forEach((p: RoomParticipant) => {
            if (p.userId !== currentUserIdRef.current) {
              peerConnections.createPeerConnection(
                p.userId,
                currentState.iceServers,
                currentState.localStream,
                true
              );
              peerConnections.createOffer(p.userId).then((offer) => {
                signaling.send({
                  type: 'offer',
                  sdp: offer,
                  targetUserId: p.userId,
                });
              });
            }
          });
          break;
        }

        case 'participant-joined': {
          logger.log('[useWebRTC] Participant joined:', message.participant.userName);
          addParticipant(message.participant);
          break;
        }

        case 'participant-left': {
          logger.log('[useWebRTC] Participant left:', message.userId);
          removeParticipant(message.userId);
          peerConnections.closePeerConnection(message.userId);
          break;
        }

        case 'offer': {
          logger.log('[useWebRTC] Received offer from:', message.fromUserId);
          let hasConnection = !!currentState.getPeerConnection(message.fromUserId);
          if (!hasConnection) {
            peerConnections.createPeerConnection(
              message.fromUserId,
              currentState.iceServers,
              currentState.localStream,
              false
            );
          }

          try {
            const answer = await peerConnections.createAnswer(message.fromUserId, message.sdp);
            signaling.send({
              type: 'answer',
              sdp: answer,
              targetUserId: message.fromUserId,
            });
          } catch (err) {
            logger.error('[useWebRTC] Failed to create answer:', err);
          }
          break;
        }

        case 'answer': {
          logger.log('[useWebRTC] Received answer from:', message.fromUserId);
          await peerConnections.setRemoteDescription(message.fromUserId, message.sdp);
          break;
        }

        case 'ice-candidate': {
          await peerConnections.addIceCandidate(message.fromUserId, message.candidate);
          break;
        }

        case 'participant-muted': {
          updateParticipantMute(message.userId, message.muted);
          break;
        }

        case 'force-muted': {
          // 자신이 강제 음소거됨
          logger.log('[useWebRTC] Force muted by:', message.byUserId, 'muted:', message.muted);
          setAudioMuted(message.muted);

          // 로컬 오디오 트랙 활성화/비활성화
          const stream = useMeetingRoomStore.getState().localStream;
          if (stream) {
            stream.getAudioTracks().forEach((track) => {
              track.enabled = !message.muted;
            });
          }
          break;
        }

        case 'screen-share-started': {
          logger.log('[useWebRTC] Screen share started by:', message.userId);
          updateParticipantScreenSharing(message.userId, true);
          break;
        }

        case 'screen-share-stopped': {
          logger.log('[useWebRTC] Screen share stopped by:', message.userId);
          updateParticipantScreenSharing(message.userId, false);
          removeRemoteScreenStream(message.userId);
          removeScreenPeerConnection(message.userId);
          break;
        }

        case 'screen-offer': {
          logger.log('[useWebRTC] Received screen offer from:', message.fromUserId);
          let pc = currentState.getScreenPeerConnection(message.fromUserId);
          if (!pc) {
            pc = screenShare.createScreenPeerConnection(message.fromUserId, currentState.iceServers);
          }

          try {
            const answer = await screenShare.createScreenAnswer(message.fromUserId, message.sdp);
            signaling.send({
              type: 'screen-answer',
              sdp: answer,
              targetUserId: message.fromUserId,
            });
          } catch (err) {
            logger.error('[useWebRTC] Failed to create screen answer:', err);
          }
          break;
        }

        case 'screen-answer': {
          logger.log('[useWebRTC] Received screen answer from:', message.fromUserId);
          await screenShare.setScreenRemoteDescription(message.fromUserId, message.sdp);
          break;
        }

        case 'screen-ice-candidate': {
          await screenShare.addScreenIceCandidate(message.fromUserId, message.candidate);
          break;
        }

        case 'meeting-ended': {
          logger.log('[useWebRTC] Meeting ended:', message.reason);
          if (stopRecordingRef.current) {
            await stopRecordingRef.current();
          }
          setConnectionState('disconnected');
          setError(message.reason);
          break;
        }

        case 'error': {
          logger.error('[useWebRTC] Error:', message.code, message.message);
          setError(message.message);
          break;
        }

        case 'chat-message': {
          // 서버에서 받은 채팅 메시지
          logger.log('[useWebRTC] Chat message received:', message.content);
          addChatMessage({
            id: message.messageId,
            userId: message.userId,
            userName: message.userName,
            content: message.content,
            createdAt: message.createdAt,
          });
          break;
        }
      }
    },
    [setParticipants, setConnectionState, addParticipant, removeParticipant, updateParticipantMute, setError, updateParticipantScreenSharing, removeRemoteScreenStream, removeScreenPeerConnection, addChatMessage]
  );

  // 시그널링 훅
  const signaling = useSignaling({
    meetingId,
    onMessage: handleSignalingMessage,
    onError: setError,
  });

  // 피어 연결 훅
  const peerConnections = usePeerConnections({
    onIceCandidate: (userId, candidate) => {
      signaling.send({
        type: 'ice-candidate',
        candidate: candidate.toJSON(),
        targetUserId: userId,
      });
    },
    onTrack: (userId, stream) => {
      logger.log('[useWebRTC] Track received from:', userId, stream);
    },
    onConnectionStateChange: (userId, state) => {
      logger.log(`[useWebRTC] Connection state with ${userId}:`, state);
    },
  });

  // 녹음 훅
  const recording = useRecording({
    meetingId,
    getLocalStream: () => useMeetingRoomStore.getState().localStream,
  });

  // recording 함수 ref 할당
  useEffect(() => {
    stopRecordingRef.current = recording.stopRecording;
    startRecordingRef.current = recording.startRecording;
  }, [recording.stopRecording, recording.startRecording]);

  // 화면공유 훅
  const screenShare = useScreenShare({
    currentUserId: currentUserIdRef.current,
    onSendMessage: signaling.send,
    onIceCandidate: (userId, candidate) => {
      signaling.send({
        type: 'screen-ice-candidate',
        candidate: candidate.toJSON(),
        targetUserId: userId,
      });
    },
  });

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
      logger.error('[useWebRTC] Failed to fetch room info:', err);
      setError('회의실 정보를 불러올 수 없습니다.');
      throw err;
    }
  }, [meetingId, setMeetingInfo, setError]);

  /**
   * 채팅 히스토리 조회
   */
  const fetchChatHistory = useCallback(async () => {
    try {
      const response = await api.get<{
        messages: Array<{
          id: string;
          user_id: string;
          user_name: string;
          content: string;
          created_at: string;
        }>;
      }>(`/meetings/${meetingId}/chat`);

      const messages = response.data.messages.map((msg) => ({
        id: msg.id,
        userId: msg.user_id,
        userName: msg.user_name,
        content: msg.content,
        createdAt: msg.created_at,
      }));

      setChatMessages(messages);
      logger.log('[useWebRTC] Chat history loaded:', messages.length, 'messages');
    } catch (err) {
      logger.warn('[useWebRTC] Failed to fetch chat history:', err);
      // 채팅 히스토리 로드 실패는 치명적이지 않으므로 에러를 throw하지 않음
    }
  }, [meetingId, setChatMessages]);

  /**
   * 회의 참여
   */
  const joinRoom = useCallback(
    async (userId: string) => {
      currentUserIdRef.current = userId;
      hasCleanedUpRef.current = false;
      setConnectionState('connecting');

      try {
        // 1. 회의실 정보 조회 및 채팅 히스토리 병렬 로드
        await Promise.all([fetchRoomInfo(), fetchChatHistory()]);

        // 2. 로컬 오디오 스트림 획득
        const currentMicGain = useMeetingRoomStore.getState().micGain;
        const processedStream = await peerConnections.initLocalStream(currentMicGain);
        setLocalStream(processedStream);

        // 3. 토큰 가져오기
        const token = localStorage.getItem('accessToken');
        if (!token) {
          throw new Error('인증 토큰이 없습니다.');
        }

        // 4. 시그널링 연결
        await signaling.connect(token);

        // 5. join 메시지 전송
        signaling.send({ type: 'join' });
      } catch (err) {
        logger.error('[useWebRTC] Failed to join room:', err);
        setConnectionState('failed');
        setError(err instanceof Error ? err.message : '회의 참여에 실패했습니다.');
        throw err;
      }
    },
    [fetchRoomInfo, fetchChatHistory, peerConnections, signaling, setConnectionState, setLocalStream, setError]
  );

  /**
   * 회의 퇴장
   */
  const leaveRoom = useCallback(async () => {
    if (hasCleanedUpRef.current) return;
    hasCleanedUpRef.current = true;
    hasStartedRecordingRef.current = false;

    // 녹음 중지 및 업로드 (항상 호출 - stopRecording 내부에서 녹음 중이 아니면 early return)
    await recording.stopRecording();

    // 시그널링 연결 해제
    signaling.disconnect();

    // 피어 연결 정리
    peerConnections.closeAllPeerConnections();
    peerConnections.cleanupLocalStream();

    // 화면공유 정리
    if (screenShare.isScreenSharing) {
      screenShare.stopScreenShare();
    }

    // 스토어 리셋
    reset();
  }, [recording, signaling, peerConnections, screenShare, reset]);

  /**
   * 오디오 음소거 토글
   */
  const toggleMute = useCallback(() => {
    const currentMuted = useMeetingRoomStore.getState().isAudioMuted;
    const newMuted = !currentMuted;
    setAudioMuted(newMuted);

    signaling.send({ type: 'mute', muted: newMuted });
  }, [setAudioMuted, signaling]);

  /**
   * 강제 음소거 (Host 전용)
   */
  const forceMute = useCallback(
    (targetUserId: string, muted: boolean) => {
      signaling.send({
        type: 'force-mute',
        targetUserId,
        muted,
      });
    },
    [signaling]
  );

  /**
   * 마이크 입력 장치 변경
   */
  const changeAudioInputDevice = useCallback(async (deviceId: string) => {
    try {
      logger.log('[useWebRTC] Changing audio input device to:', deviceId);

      const currentMicGain = useMeetingRoomStore.getState().micGain;
      const newStream = await peerConnections.initLocalStream(currentMicGain, deviceId);

      // 현재 음소거 상태 유지
      const currentMuted = useMeetingRoomStore.getState().isAudioMuted;
      if (currentMuted) {
        newStream.getAudioTracks().forEach((track) => {
          track.enabled = false;
        });
      }

      // 모든 피어 연결에 새 트랙 교체
      const newTrack = newStream.getAudioTracks()[0];
      const currentState = useMeetingRoomStore.getState();
      for (const [peerId] of currentState.peerConnections) {
        await peerConnections.replaceTrack(peerId, newTrack);
      }

      setLocalStream(newStream);
      setAudioInputDeviceId(deviceId);

      logger.log('[useWebRTC] Audio input device changed successfully');
    } catch (err) {
      logger.error('[useWebRTC] Failed to change audio input device:', err);
      throw err;
    }
  }, [peerConnections, setLocalStream, setAudioInputDeviceId]);

  /**
   * 스피커 출력 장치 변경
   */
  const changeAudioOutputDevice = useCallback((deviceId: string) => {
    setAudioOutputDeviceId(deviceId);
    logger.log('[useWebRTC] Audio output device changed to:', deviceId);
  }, [setAudioOutputDeviceId]);

  /**
   * 마이크 gain 변경
   */
  const changeMicGain = useCallback((gain: number) => {
    const clampedGain = Math.max(0, Math.min(2, gain));
    peerConnections.changeMicGain(clampedGain);
    setMicGain(clampedGain);
    logger.log('[useWebRTC] Mic gain changed to:', clampedGain);
  }, [peerConnections, setMicGain]);

  /**
   * 원격 참여자 볼륨 변경
   */
  const changeRemoteVolume = useCallback((userId: string, volume: number) => {
    const clampedVolume = Math.max(0, Math.min(2, volume));
    setRemoteVolume(userId, clampedVolume);
    logger.log(`[useWebRTC] Remote volume for ${userId} changed to:`, clampedVolume);
  }, [setRemoteVolume]);

  /**
   * 화면공유 시작
   */
  const startScreenShare = useCallback(async () => {
    const currentState = useMeetingRoomStore.getState();
    await screenShare.startScreenShare(currentState.iceServers, currentState.participants);
  }, [screenShare]);

  /**
   * 화면공유 중지
   */
  const stopScreenShare = useCallback(() => {
    screenShare.stopScreenShare();
  }, [screenShare]);

  /**
   * 채팅 메시지 전송
   */
  const sendChatMessage = useCallback(
    (content: string) => {
      signaling.send({
        type: 'chat-message',
        content,
      });
    },
    [signaling]
  );

  /**
   * 연결 완료 시 자동 녹음 시작
   * ref를 사용하여 녹음 시작 여부 추적 및 함수 호출 (의존성 제거)
   */
  useEffect(() => {
    if (connectionState === 'connected' && !hasStartedRecordingRef.current) {
      hasStartedRecordingRef.current = true;
      logger.log('[useWebRTC] Auto-starting recording in 500ms...');
      const timer = setTimeout(() => {
        logger.log('[useWebRTC] Auto-starting recording now');
        startRecordingRef.current?.();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [connectionState]);

  /**
   * 마운트 시 이전 녹음 데이터 업로드
   */
  useEffect(() => {
    recording.uploadPendingRecordings();
  }, [recording.uploadPendingRecordings]);

  /**
   * 회의 중 주기적 토큰 갱신
   */
  useEffect(() => {
    if (connectionState !== 'connected') {
      return;
    }

    logger.log('[useWebRTC] Starting periodic token refresh...');
    ensureValidToken();

    const intervalId = setInterval(() => {
      logger.log('[useWebRTC] Periodic token refresh check...');
      ensureValidToken();
    }, TOKEN_REFRESH_INTERVAL);

    return () => {
      logger.log('[useWebRTC] Stopping periodic token refresh');
      clearInterval(intervalId);
    };
  }, [connectionState]);

  /**
   * cleanup - 컴포넌트 언마운트 시에만 실행
   */
  useEffect(() => {
    return () => {
      if (!hasCleanedUpRef.current) {
        hasCleanedUpRef.current = true;
        signaling.disconnect();
        peerConnections.closeAllPeerConnections();
        peerConnections.cleanupLocalStream();
        reset();
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
    isRecording: recording.isRecording,
    recordingError: recording.recordingError,
    isUploading: recording.isUploading,
    uploadProgress: recording.uploadProgress,
    audioInputDeviceId,
    audioOutputDeviceId,
    micGain,
    remoteVolumes,
    // 화면공유 상태
    isScreenSharing: screenShare.isScreenSharing,
    screenStream: screenShare.screenStream,
    remoteScreenStreams: screenShare.remoteScreenStreams,
    // 채팅 상태
    chatMessages,

    // 액션
    joinRoom,
    leaveRoom,
    toggleMute,
    forceMute,
    changeAudioInputDevice,
    changeAudioOutputDevice,
    changeMicGain,
    changeRemoteVolume,
    // 화면공유 액션
    startScreenShare,
    stopScreenShare,
    // 채팅 액션
    sendChatMessage,
  };
}
