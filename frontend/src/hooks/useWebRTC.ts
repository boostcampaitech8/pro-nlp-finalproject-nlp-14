/**
 * WebRTC 훅
 * 시그널링 및 피어 연결 관리
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { signalingClient } from '@/services/signalingService';
import { webrtcService } from '@/services/webrtcService';
import { recordingService } from '@/services/recordingService';
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

  // 녹음 관련 상태 (클라이언트 측 MediaRecorder)
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingStartTimeRef = useRef<Date | null>(null);

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
   * 회의 퇴장 (녹음 업로드 완료 후)
   */
  const leaveRoom = useCallback(async () => {
    if (hasCleanedUpRef.current) return;
    hasCleanedUpRef.current = true;

    // 녹음 중이면 중지하고 업로드 (완료될 때까지 대기)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      console.log('[useWebRTC] Stopping recording before leaving...');
      await stopRecordingInternal();
    }

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
   * 녹음 시작 (내부 함수) - 회의 연결 시 자동 호출
   */
  const startRecordingInternal = useCallback(() => {
    if (isRecording || mediaRecorderRef.current) {
      console.log('[useWebRTC] Already recording');
      return;
    }

    const currentState = useMeetingRoomStore.getState();
    if (!currentState.localStream) {
      console.error('[useWebRTC] No local stream for recording');
      setRecordingError('로컬 오디오 스트림이 없습니다.');
      return;
    }

    // 이전 에러 초기화
    setRecordingError(null);
    recordedChunksRef.current = [];

    try {
      console.log('[useWebRTC] Starting recording with MediaRecorder...');

      // MediaRecorder 생성
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const mediaRecorder = new MediaRecorder(currentState.localStream, {
        mimeType,
        audioBitsPerSecond: 128000,
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onerror = (event) => {
        console.error('[useWebRTC] MediaRecorder error:', event);
        setRecordingError('녹음 중 오류가 발생했습니다.');
        setIsRecording(false);
      };

      mediaRecorder.onstop = () => {
        console.log('[useWebRTC] MediaRecorder stopped');
      };

      mediaRecorderRef.current = mediaRecorder;
      recordingStartTimeRef.current = new Date();

      // 녹음 시작 (1초마다 데이터 수집)
      mediaRecorder.start(1000);
      setIsRecording(true);

      console.log('[useWebRTC] Recording started automatically');
    } catch (err) {
      console.error('[useWebRTC] Failed to start recording:', err);
      setRecordingError('녹음을 시작할 수 없습니다.');
      mediaRecorderRef.current = null;
    }
  }, [isRecording]);

  /**
   * 녹음 중지 및 서버 업로드 (내부 함수) - 회의 퇴장 시 자동 호출
   */
  const stopRecordingInternal = useCallback(async () => {
    if (!mediaRecorderRef.current || !recordingStartTimeRef.current) {
      console.log('[useWebRTC] No active recording');
      return;
    }

    console.log('[useWebRTC] Stopping recording and uploading...');

    return new Promise<void>((resolve) => {
      const mediaRecorder = mediaRecorderRef.current!;
      const startTime = recordingStartTimeRef.current!;

      mediaRecorder.onstop = async () => {
        const endTime = new Date();
        const durationMs = endTime.getTime() - startTime.getTime();

        // Blob 생성
        const blob = new Blob(recordedChunksRef.current, { type: 'audio/webm' });
        console.log(`[useWebRTC] Recording blob created: ${blob.size} bytes, ${durationMs}ms`);

        // 녹음 파일이 비어있지 않으면 업로드
        if (blob.size > 0) {
          setIsUploading(true);
          try {
            await recordingService.uploadRecording({
              meetingId,
              file: blob,
              startedAt: startTime,
              endedAt: endTime,
              durationMs,
            });
            console.log('[useWebRTC] Recording uploaded successfully');
          } catch (err) {
            console.error('[useWebRTC] Failed to upload recording:', err);
            setRecordingError('녹음 업로드에 실패했습니다.');
          } finally {
            setIsUploading(false);
          }
        }

        // 상태 초기화
        mediaRecorderRef.current = null;
        recordingStartTimeRef.current = null;
        recordedChunksRef.current = [];
        setIsRecording(false);

        resolve();
      };

      // 녹음 중지
      if (mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
      } else {
        mediaRecorderRef.current = null;
        recordingStartTimeRef.current = null;
        recordedChunksRef.current = [];
        setIsRecording(false);
        resolve();
      }
    });
  }, [meetingId]);

  /**
   * 연결 완료 시 자동 녹음 시작
   */
  useEffect(() => {
    if (connectionState === 'connected' && !isRecording && !mediaRecorderRef.current) {
      // 약간의 딜레이 후 녹음 시작 (스트림 안정화)
      const timer = setTimeout(() => {
        startRecordingInternal();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [connectionState, isRecording, startRecordingInternal]);

  /**
   * cleanup - 빈 의존성 배열로 마운트/언마운트 시에만 실행
   */
  useEffect(() => {
    return () => {
      // 녹음 정리 (MediaRecorder)
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
        mediaRecorderRef.current = null;
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
    recordingError,
    isUploading,

    // 액션
    joinRoom,
    leaveRoom,
    toggleMute,
  };
}
