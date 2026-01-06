/**
 * WebRTC 훅
 * 시그널링 및 피어 연결 관리
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { signalingClient } from '@/services/signalingService';
import { webrtcService, type ProcessedAudioStream } from '@/services/webrtcService';
import { recordingService } from '@/services/recordingService';
import { recordingStorageService } from '@/services/recordingStorageService';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import type { ServerMessage, RoomParticipant, MeetingRoomResponse } from '@/types/webrtc';
import api, { ensureValidToken } from '@/services/api';

// 토큰 갱신 주기 (15분)
const TOKEN_REFRESH_INTERVAL = 15 * 60 * 1000;

// 녹음 임시 저장 주기 (10초)
const RECORDING_SAVE_INTERVAL = 10 * 1000;

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
  const audioInputDeviceId = useMeetingRoomStore((s) => s.audioInputDeviceId);
  const audioOutputDeviceId = useMeetingRoomStore((s) => s.audioOutputDeviceId);
  const micGain = useMeetingRoomStore((s) => s.micGain);
  const setAudioInputDeviceId = useMeetingRoomStore((s) => s.setAudioInputDeviceId);
  const setAudioOutputDeviceId = useMeetingRoomStore((s) => s.setAudioOutputDeviceId);
  const setMicGain = useMeetingRoomStore((s) => s.setMicGain);
  const addRemoteStream = useMeetingRoomStore((s) => s.addRemoteStream);
  const remoteVolumes = useMeetingRoomStore((s) => s.remoteVolumes);
  const setRemoteVolume = useMeetingRoomStore((s) => s.setRemoteVolume);
  const addPeerConnection = useMeetingRoomStore((s) => s.addPeerConnection);
  const removePeerConnection = useMeetingRoomStore((s) => s.removePeerConnection);
  const reset = useMeetingRoomStore((s) => s.reset);

  // 화면공유 관련 selector
  const isScreenSharing = useMeetingRoomStore((s) => s.isScreenSharing);
  const screenStream = useMeetingRoomStore((s) => s.screenStream);
  const remoteScreenStreams = useMeetingRoomStore((s) => s.remoteScreenStreams);
  const setScreenSharing = useMeetingRoomStore((s) => s.setScreenSharing);
  const setScreenStream = useMeetingRoomStore((s) => s.setScreenStream);
  const addRemoteScreenStream = useMeetingRoomStore((s) => s.addRemoteScreenStream);
  const removeRemoteScreenStream = useMeetingRoomStore((s) => s.removeRemoteScreenStream);
  const addScreenPeerConnection = useMeetingRoomStore((s) => s.addScreenPeerConnection);
  const removeScreenPeerConnection = useMeetingRoomStore((s) => s.removeScreenPeerConnection);
  const updateParticipantScreenSharing = useMeetingRoomStore((s) => s.updateParticipantScreenSharing);

  const currentUserIdRef = useRef<string>('');
  const hasCleanedUpRef = useRef(false);

  // GainNode 처리 관련 ref
  const processedAudioRef = useRef<ProcessedAudioStream | null>(null);
  const rawStreamRef = useRef<MediaStream | null>(null);

  // 녹음 관련 상태 (클라이언트 측 MediaRecorder)
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingStartTimeRef = useRef<Date | null>(null);
  const recordingIdRef = useRef<string | null>(null); // IndexedDB 저장용 ID
  const saveIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null); // 주기적 저장 타이머
  const lastSavedChunkIndexRef = useRef<number>(-1); // 마지막으로 IndexedDB에 저장된 청크 인덱스
  const stopRecordingAndUploadRef = useRef<() => Promise<void>>(); // 녹음 중지 및 업로드 함수 ref

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
   * 화면공유용 피어 연결 생성 (수신 전용)
   */
  const createScreenPeerConnectionForUser = useCallback(
    (userId: string, currentIceServers: typeof iceServers) => {
      const pc = webrtcService.createPeerConnection(
        currentIceServers,
        // ICE Candidate 콜백
        (candidate) => {
          signalingClient.send({
            type: 'screen-ice-candidate',
            candidate: candidate.toJSON(),
            targetUserId: userId,
          });
        },
        // Track 수신 콜백 (화면공유 비디오 트랙)
        (event) => {
          console.log('[useWebRTC] Screen track received from:', userId);
          if (event.streams && event.streams[0]) {
            addRemoteScreenStream(userId, event.streams[0]);
          }
        },
        // 연결 상태 변경 콜백
        (state) => {
          console.log(`[useWebRTC] Screen connection state with ${userId}:`, state);
          if (state === 'failed' || state === 'disconnected') {
            removeScreenPeerConnection(userId);
            removeRemoteScreenStream(userId);
          }
        }
      );

      addScreenPeerConnection(userId, pc);
      return pc;
    },
    [addRemoteScreenStream, removeRemoteScreenStream, addScreenPeerConnection, removeScreenPeerConnection]
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

        // 화면공유 관련 메시지
        case 'screen-share-started': {
          console.log('[useWebRTC] Screen share started by:', message.userId);
          updateParticipantScreenSharing(message.userId, true);
          break;
        }

        case 'screen-share-stopped': {
          console.log('[useWebRTC] Screen share stopped by:', message.userId);
          updateParticipantScreenSharing(message.userId, false);
          removeRemoteScreenStream(message.userId);
          removeScreenPeerConnection(message.userId);
          break;
        }

        case 'screen-offer': {
          console.log('[useWebRTC] Received screen offer from:', message.fromUserId);
          // 화면공유용 피어 연결 생성 및 answer
          let pc = currentState.getScreenPeerConnection(message.fromUserId);
          if (!pc) {
            pc = createScreenPeerConnectionForUser(message.fromUserId, currentState.iceServers);
          }

          try {
            const answer = await webrtcService.createAnswer(pc, message.sdp);
            signalingClient.send({
              type: 'screen-answer',
              sdp: answer,
              targetUserId: message.fromUserId,
            });
          } catch (err) {
            console.error('[useWebRTC] Failed to create screen answer:', err);
          }
          break;
        }

        case 'screen-answer': {
          console.log('[useWebRTC] Received screen answer from:', message.fromUserId);
          const pc = currentState.getScreenPeerConnection(message.fromUserId);
          if (pc) {
            await webrtcService.setRemoteDescription(pc, message.sdp);
          }
          break;
        }

        case 'screen-ice-candidate': {
          const pc = currentState.getScreenPeerConnection(message.fromUserId);
          if (pc) {
            await webrtcService.addIceCandidate(pc, message.candidate);
          }
          break;
        }

        case 'meeting-ended': {
          console.log('[useWebRTC] Meeting ended:', message.reason);
          // 녹음 중이면 업로드 수행
          if (stopRecordingAndUploadRef.current) {
            console.log('[useWebRTC] Uploading recording before meeting end...');
            stopRecordingAndUploadRef.current().then(() => {
              console.log('[useWebRTC] Recording uploaded after meeting end');
            }).catch((err) => {
              console.error('[useWebRTC] Failed to upload recording on meeting end:', err);
            });
          }
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
    [setParticipants, setConnectionState, addParticipant, removeParticipant, updateParticipantMute, setError, createPeerConnectionForUser, updateParticipantScreenSharing, removeRemoteScreenStream, removeScreenPeerConnection, createScreenPeerConnectionForUser]
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

        // 2. 로컬 오디오 스트림 획득 및 GainNode 처리
        const rawStream = await webrtcService.getLocalAudioStream();
        rawStreamRef.current = rawStream;

        // GainNode를 통해 처리된 스트림 생성
        const currentMicGain = useMeetingRoomStore.getState().micGain;
        const processed = webrtcService.createProcessedAudioStream(rawStream, currentMicGain);
        processedAudioRef.current = processed;

        // 처리된 스트림을 로컬 스트림으로 사용
        setLocalStream(processed.processedStream);

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
   * 마이크 입력 장치 변경
   */
  const changeAudioInputDevice = useCallback(async (deviceId: string) => {
    try {
      console.log('[useWebRTC] Changing audio input device to:', deviceId);

      // 1. 새 장치로 스트림 획득
      const newStream = await webrtcService.getLocalAudioStream(deviceId);

      // 2. 현재 음소거 상태 유지
      const currentMuted = useMeetingRoomStore.getState().isAudioMuted;
      if (currentMuted) {
        newStream.getAudioTracks().forEach((track) => {
          track.enabled = false;
        });
      }

      // 3. 기존 스트림 정리
      const currentState = useMeetingRoomStore.getState();
      if (currentState.localStream) {
        currentState.localStream.getTracks().forEach((track) => track.stop());
      }

      // 4. 모든 피어 연결에 새 트랙 교체 (RTCRtpSender.replaceTrack)
      const newTrack = newStream.getAudioTracks()[0];
      currentState.peerConnections.forEach((pc, peerId) => {
        const senders = pc.getSenders();
        const audioSender = senders.find((s) => s.track?.kind === 'audio');
        if (audioSender) {
          audioSender.replaceTrack(newTrack).catch((err) => {
            console.error(`[useWebRTC] Failed to replace track for peer ${peerId}:`, err);
          });
        }
      });

      // 5. 스토어 업데이트
      setLocalStream(newStream);
      setAudioInputDeviceId(deviceId);

      console.log('[useWebRTC] Audio input device changed successfully');
    } catch (err) {
      console.error('[useWebRTC] Failed to change audio input device:', err);
      throw err;
    }
  }, [setLocalStream, setAudioInputDeviceId]);

  /**
   * 스피커 출력 장치 변경
   */
  const changeAudioOutputDevice = useCallback((deviceId: string) => {
    setAudioOutputDeviceId(deviceId);
    console.log('[useWebRTC] Audio output device changed to:', deviceId);
  }, [setAudioOutputDeviceId]);

  /**
   * 마이크 gain 변경
   */
  const changeMicGain = useCallback((gain: number) => {
    // gain 값 범위 제한 (0.0 ~ 2.0)
    const clampedGain = Math.max(0, Math.min(2, gain));

    // GainNode 값 업데이트
    if (processedAudioRef.current) {
      processedAudioRef.current.gainNode.gain.value = clampedGain;
    }

    // 스토어 업데이트
    setMicGain(clampedGain);
    console.log('[useWebRTC] Mic gain changed to:', clampedGain);
  }, [setMicGain]);

  /**
   * 원격 참여자 볼륨 변경
   */
  const changeRemoteVolume = useCallback((userId: string, volume: number) => {
    // 볼륨 값 범위 제한 (0.0 ~ 2.0)
    const clampedVolume = Math.max(0, Math.min(2, volume));
    setRemoteVolume(userId, clampedVolume);
    console.log(`[useWebRTC] Remote volume for ${userId} changed to:`, clampedVolume);
  }, [setRemoteVolume]);

  /**
   * 화면공유 시작
   */
  const startScreenShare = useCallback(async () => {
    const currentState = useMeetingRoomStore.getState();

    if (currentState.isScreenSharing) {
      console.log('[useWebRTC] Already sharing screen');
      return;
    }

    try {
      // 1. 화면공유 스트림 획득
      const stream = await webrtcService.getDisplayMediaStream();
      setScreenStream(stream);
      setScreenSharing(true);

      // 화면공유 중지 이벤트 리스너 (사용자가 브라우저 UI로 중지할 경우)
      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.onended = () => {
          console.log('[useWebRTC] Screen share track ended by user');
          stopScreenShare();
        };
      }

      // 2. 서버에 화면공유 시작 알림
      signalingClient.send({ type: 'screen-share-start' });

      // 3. 모든 참여자에게 화면공유 피어 연결 생성 및 offer 전송
      const latestState = useMeetingRoomStore.getState();
      latestState.participants.forEach((participant) => {
        if (participant.userId !== currentUserIdRef.current) {
          // 화면공유용 피어 연결 생성
          const pc = webrtcService.createPeerConnection(
            latestState.iceServers,
            // ICE Candidate 콜백
            (candidate) => {
              signalingClient.send({
                type: 'screen-ice-candidate',
                candidate: candidate.toJSON(),
                targetUserId: participant.userId,
              });
            },
            // Track 수신 콜백 (화면공유에서는 사용하지 않음)
            () => {},
            // 연결 상태 변경 콜백
            (state) => {
              console.log(`[useWebRTC] Screen connection state with ${participant.userId}:`, state);
            }
          );

          // 비디오 트랙 추가
          stream.getTracks().forEach((track) => {
            webrtcService.addTrack(pc, track, stream);
          });

          addScreenPeerConnection(participant.userId, pc);

          // Offer 생성 및 전송
          webrtcService.createOffer(pc).then((offer) => {
            signalingClient.send({
              type: 'screen-offer',
              sdp: offer,
              targetUserId: participant.userId,
            });
          }).catch((err) => {
            console.error(`[useWebRTC] Failed to create screen offer for ${participant.userId}:`, err);
          });
        }
      });

      console.log('[useWebRTC] Screen sharing started');
    } catch (err) {
      console.error('[useWebRTC] Failed to start screen share:', err);
      setScreenSharing(false);
      setScreenStream(null);
      throw err;
    }
  }, [setScreenStream, setScreenSharing, addScreenPeerConnection]);

  /**
   * 화면공유 중지
   */
  const stopScreenShare = useCallback(() => {
    const currentState = useMeetingRoomStore.getState();

    if (!currentState.isScreenSharing) {
      console.log('[useWebRTC] Not sharing screen');
      return;
    }

    // 1. 서버에 화면공유 중지 알림
    signalingClient.send({ type: 'screen-share-stop' });

    // 2. 화면공유 피어 연결 정리
    currentState.screenPeerConnections.forEach((pc, userId) => {
      pc.close();
      removeScreenPeerConnection(userId);
    });

    // 3. 스트림 정리
    setScreenStream(null);
    setScreenSharing(false);

    console.log('[useWebRTC] Screen sharing stopped');
  }, [setScreenStream, setScreenSharing, removeScreenPeerConnection]);

  /**
   * 녹음 청크를 IndexedDB에 증분 저장 (새로운 청크만)
   */
  const saveChunksToStorage = useCallback(async () => {
    if (!recordingIdRef.current || !recordingStartTimeRef.current) return;
    if (recordedChunksRef.current.length === 0) return;

    try {
      const newLastIndex = await recordingStorageService.saveNewChunks(
        recordingIdRef.current,
        meetingId,
        recordedChunksRef.current,
        recordingStartTimeRef.current,
        lastSavedChunkIndexRef.current
      );
      lastSavedChunkIndexRef.current = newLastIndex;
    } catch (err) {
      console.error('[useWebRTC] Failed to save chunks to storage:', err);
    }
  }, [meetingId]);

  /**
   * IndexedDB에 저장된 이전 녹음 데이터 업로드
   */
  const uploadPendingRecordings = useCallback(async () => {
    try {
      // 24시간 이상 된 오래된 녹음 정리
      await recordingStorageService.cleanupOldRecordings();

      // 현재 회의에 대한 대기 중인 녹음 조회
      const pendingRecordings = await recordingStorageService.getRecordingsByMeeting(meetingId);

      if (pendingRecordings.length === 0) {
        console.log('[useWebRTC] No pending recordings to upload');
        // localStorage 백업도 확인
        const backupStr = localStorage.getItem('mit-recording-backup');
        if (backupStr) {
          try {
            const backup = JSON.parse(backupStr);
            if (backup.meetingId === meetingId) {
              console.log('[useWebRTC] Found localStorage backup, but no chunks in IndexedDB');
              localStorage.removeItem('mit-recording-backup');
            }
          } catch {
            localStorage.removeItem('mit-recording-backup');
          }
        }
        return;
      }

      console.log(`[useWebRTC] Found ${pendingRecordings.length} pending recordings to upload`);

      for (const recording of pendingRecordings) {
        if (recording.chunks.length === 0) {
          await recordingStorageService.deleteRecording(recording.id);
          continue;
        }

        try {
          // 토큰 유효성 확인
          await ensureValidToken();

          const blob = recordingStorageService.mergeChunks(recording.chunks);
          const endTime = new Date(recording.lastUpdatedAt);
          const durationMs = endTime.getTime() - new Date(recording.startedAt).getTime();

          console.log(`[useWebRTC] Uploading pending recording ${recording.id}: ${blob.size} bytes`);

          await recordingService.uploadRecordingPresigned(
            {
              meetingId: recording.meetingId,
              file: blob,
              startedAt: new Date(recording.startedAt),
              endedAt: endTime,
              durationMs,
            },
            (progress) => {
              console.log(`[useWebRTC] Pending upload progress: ${progress}%`);
            }
          );

          // 업로드 성공 시 삭제
          await recordingStorageService.deleteRecording(recording.id);
          console.log(`[useWebRTC] Pending recording ${recording.id} uploaded and deleted`);
        } catch (err) {
          console.error(`[useWebRTC] Failed to upload pending recording ${recording.id}:`, err);
          // 업로드 실패 시 다음 기회에 재시도하도록 유지
        }
      }

      // localStorage 백업 정리
      localStorage.removeItem('mit-recording-backup');
    } catch (err) {
      console.error('[useWebRTC] Failed to process pending recordings:', err);
    }
  }, [meetingId]);

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
    lastSavedChunkIndexRef.current = -1; // 증분 저장 인덱스 초기화

    // 녹음 ID 생성 (meetingId_timestamp)
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    recordingIdRef.current = `${meetingId}_${timestamp}`;

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
        // 주기적 저장 중지
        if (saveIntervalRef.current) {
          clearInterval(saveIntervalRef.current);
          saveIntervalRef.current = null;
        }
      };

      mediaRecorder.onstop = () => {
        console.log('[useWebRTC] MediaRecorder stopped');
        // 주기적 저장 중지
        if (saveIntervalRef.current) {
          clearInterval(saveIntervalRef.current);
          saveIntervalRef.current = null;
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      recordingStartTimeRef.current = new Date();

      // 녹음 시작 (1초마다 데이터 수집)
      mediaRecorder.start(1000);
      setIsRecording(true);

      // 주기적으로 IndexedDB에 저장 (10초마다)
      saveIntervalRef.current = setInterval(() => {
        saveChunksToStorage();
      }, RECORDING_SAVE_INTERVAL);

      console.log('[useWebRTC] Recording started automatically with periodic save');
    } catch (err) {
      console.error('[useWebRTC] Failed to start recording:', err);
      setRecordingError('녹음을 시작할 수 없습니다.');
      mediaRecorderRef.current = null;
      recordingIdRef.current = null;
    }
  }, [isRecording, meetingId, saveChunksToStorage]);

  /**
   * 녹음 중지 및 서버 업로드 (내부 함수) - 회의 퇴장 시 자동 호출
   */
  const stopRecordingInternal = useCallback(async () => {
    // 주기적 저장 중지
    if (saveIntervalRef.current) {
      clearInterval(saveIntervalRef.current);
      saveIntervalRef.current = null;
    }

    if (!mediaRecorderRef.current || !recordingStartTimeRef.current) {
      console.log('[useWebRTC] No active recording');
      return;
    }

    console.log('[useWebRTC] Stopping recording and uploading...');
    const currentRecordingId = recordingIdRef.current;
    const startTime = recordingStartTimeRef.current;

    return new Promise<void>((resolve) => {
      const mediaRecorder = mediaRecorderRef.current!;

      mediaRecorder.onstop = async () => {
        const endTime = new Date();
        const durationMs = endTime.getTime() - startTime.getTime();

        // 1. 메모리의 남은 청크를 IndexedDB에 증분 저장
        if (currentRecordingId && recordedChunksRef.current.length > lastSavedChunkIndexRef.current + 1) {
          try {
            await recordingStorageService.saveNewChunks(
              currentRecordingId,
              meetingId,
              recordedChunksRef.current,
              startTime,
              lastSavedChunkIndexRef.current
            );
            console.log('[useWebRTC] Saved remaining chunks to IndexedDB before upload');
          } catch (err) {
            console.error('[useWebRTC] Failed to save remaining chunks:', err);
          }
        }

        // 2. IndexedDB에서 모든 청크 조회하여 병합
        let allChunks: Blob[] = recordedChunksRef.current; // 기본값: 메모리 청크
        if (currentRecordingId) {
          try {
            const storedChunks = await recordingStorageService.getChunks(currentRecordingId);
            if (storedChunks.length > 0) {
              allChunks = storedChunks;
              console.log(`[useWebRTC] Retrieved ${storedChunks.length} chunks from IndexedDB`);
            }
          } catch (err) {
            console.error('[useWebRTC] Failed to get chunks from IndexedDB, using memory chunks:', err);
          }
        }

        // 3. 청크 병합하여 Blob 생성
        const blob = recordingStorageService.mergeChunks(allChunks);
        console.log(`[useWebRTC] Recording blob created: ${blob.size} bytes, ${durationMs}ms, ${allChunks.length} chunks`);

        // 4. 녹음 파일이 비어있지 않으면 업로드 (Presigned URL 방식)
        if (blob.size > 0) {
          setIsUploading(true);
          setUploadProgress(0);
          try {
            // 업로드 전 토큰 유효성 확인 및 갱신
            await ensureValidToken();

            await recordingService.uploadRecordingPresigned(
              {
                meetingId,
                file: blob,
                startedAt: startTime,
                endedAt: endTime,
                durationMs,
              },
              (progress) => {
                setUploadProgress(progress);
                console.log(`[useWebRTC] Upload progress: ${progress}%`);
              }
            );
            console.log('[useWebRTC] Recording uploaded successfully via presigned URL');

            // 업로드 성공 시 IndexedDB에서 삭제
            if (currentRecordingId) {
              await recordingStorageService.deleteRecording(currentRecordingId);
              console.log('[useWebRTC] Deleted recording from IndexedDB:', currentRecordingId);
            }
          } catch (err) {
            console.error('[useWebRTC] Failed to upload recording:', err);
            setRecordingError('녹음 업로드에 실패했습니다.');
            // 업로드 실패해도 IndexedDB에는 이미 저장되어 있으므로 다음에 재시도 가능
            console.log('[useWebRTC] Recording saved in IndexedDB for retry');
          } finally {
            setIsUploading(false);
            setUploadProgress(0);
          }
        }

        // 5. 상태 초기화
        mediaRecorderRef.current = null;
        recordingStartTimeRef.current = null;
        recordedChunksRef.current = [];
        recordingIdRef.current = null;
        lastSavedChunkIndexRef.current = -1;
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
        recordingIdRef.current = null;
        lastSavedChunkIndexRef.current = -1;
        setIsRecording(false);
        resolve();
      }
    });
  }, [meetingId]);

  /**
   * stopRecordingAndUploadRef 할당 (meeting-ended 이벤트에서 사용)
   */
  useEffect(() => {
    stopRecordingAndUploadRef.current = stopRecordingInternal;
  }, [stopRecordingInternal]);

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
   * beforeunload 이벤트 - 새로고침/탭 닫기 시 녹음 데이터 임시저장
   */
  useEffect(() => {
    const handleBeforeUnload = () => {
      // 녹음 중이면 현재까지의 청크를 IndexedDB에 저장
      if (recordingIdRef.current && recordingStartTimeRef.current && recordedChunksRef.current.length > 0) {
        // 동기적으로 저장 시도 (sendBeacon 또는 동기 localStorage 백업)
        // IndexedDB는 비동기라 beforeunload에서 완료 보장 불가 -> localStorage 임시 백업
        try {
          const backupData = {
            id: recordingIdRef.current,
            meetingId,
            startedAt: recordingStartTimeRef.current.toISOString(),
            chunkCount: recordedChunksRef.current.length,
            timestamp: Date.now(),
          };
          localStorage.setItem('mit-recording-backup', JSON.stringify(backupData));
          console.log('[useWebRTC] Saved recording backup to localStorage');
        } catch (err) {
          console.error('[useWebRTC] Failed to save recording backup:', err);
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [meetingId]);

  /**
   * 컴포넌트 마운트 시 이전 임시저장 녹음 데이터 업로드
   */
  useEffect(() => {
    uploadPendingRecordings();
  }, [uploadPendingRecordings]);

  /**
   * 회의 중 주기적 토큰 갱신
   * 30분 만료 토큰이므로 15분마다 갱신하여 회의 중 토큰 만료 방지
   */
  useEffect(() => {
    if (connectionState !== 'connected') {
      return;
    }

    console.log('[useWebRTC] Starting periodic token refresh...');

    // 즉시 한 번 체크
    ensureValidToken();

    // 주기적으로 토큰 갱신
    const intervalId = setInterval(() => {
      console.log('[useWebRTC] Periodic token refresh check...');
      ensureValidToken();
    }, TOKEN_REFRESH_INTERVAL);

    return () => {
      console.log('[useWebRTC] Stopping periodic token refresh');
      clearInterval(intervalId);
    };
  }, [connectionState]);

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

      // GainNode 리소스 정리
      if (processedAudioRef.current) {
        processedAudioRef.current.cleanup();
        processedAudioRef.current = null;
      }

      // Raw 스트림 정리
      if (rawStreamRef.current) {
        rawStreamRef.current.getTracks().forEach((track) => track.stop());
        rawStreamRef.current = null;
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
    uploadProgress,
    audioInputDeviceId,
    audioOutputDeviceId,
    micGain,
    remoteVolumes,
    // 화면공유 상태
    isScreenSharing,
    screenStream,
    remoteScreenStreams,

    // 액션
    joinRoom,
    leaveRoom,
    toggleMute,
    changeAudioInputDevice,
    changeAudioOutputDevice,
    changeMicGain,
    changeRemoteVolume,
    // 화면공유 액션
    startScreenShare,
    stopScreenShare,
  };
}
