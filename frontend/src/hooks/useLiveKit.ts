/**
 * LiveKit SFU 연결 훅
 * 기존 useWebRTC와 동일한 인터페이스 유지
 *
 * - LiveKit Room 연결 및 관리
 * - 오디오/화면공유 트랙 관리
 * - DataPacket을 통한 VAD 이벤트 및 채팅 전송
 * - Web Audio API GainNode를 통한 마이크 게인 및 원격 볼륨 제어
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Room,
  RoomEvent,
  ConnectionState as LiveKitConnectionState,
  Track,
  Participant,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
  LocalTrack,
  createLocalTracks,
  LocalAudioTrack,
  DisconnectReason,
  LogLevel,
  setLogLevel,
} from 'livekit-client';
import api, { ensureValidToken } from '@/services/api';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import type { ConnectionState, RoomParticipant } from '@/types/webrtc';
import logger from '@/utils/logger';
import { useVAD, type VADSegment } from './useVAD';

// 토큰 갱신 주기 (15분)
const TOKEN_REFRESH_INTERVAL = 15 * 60 * 1000;

// 디버그 모드 (환경변수로 제어)
const isDevMode = import.meta.env.VITE_DEV_MODE === 'true';

// LiveKit SDK 로그 레벨 설정
setLogLevel(isDevMode ? LogLevel.debug : LogLevel.warn);

// DataPacket 메시지 타입
interface DataMessage {
  type: 'vad_event' | 'chat_message' | 'force_mute' | 'mute_state';
  payload: unknown;
}

interface VADEventPayload {
  eventType: 'speech_start' | 'speech_end';
  segmentStartMs?: number;
  segmentEndMs?: number;
  timestamp: string;
}

interface ChatMessagePayload {
  id: string;
  content: string;
  userName: string;
  createdAt: string;
}

interface ForceMutePayload {
  targetUserId: string;
  muted: boolean;
}

interface MuteStatePayload {
  muted: boolean;
}

// LiveKit 토큰 응답
interface LiveKitTokenResponse {
  token: string;
  wsUrl: string;
  roomName: string;
}

// 녹음 시작 응답
interface StartRecordingResponse {
  meetingId: string;
  egressId: string;
  startedAt: string;
}

export function useLiveKit(meetingId: string) {
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
  const addRemoteStream = useMeetingRoomStore((s) => s.addRemoteStream);
  const removeRemoteStream = useMeetingRoomStore((s) => s.removeRemoteStream);
  const setRemoteVolume = useMeetingRoomStore((s) => s.setRemoteVolume);
  const updateParticipantScreenSharing = useMeetingRoomStore((s) => s.updateParticipantScreenSharing);
  const setScreenSharing = useMeetingRoomStore((s) => s.setScreenSharing);
  const setScreenStream = useMeetingRoomStore((s) => s.setScreenStream);
  const addRemoteScreenStream = useMeetingRoomStore((s) => s.addRemoteScreenStream);
  const removeRemoteScreenStream = useMeetingRoomStore((s) => s.removeRemoteScreenStream);
  const chatMessages = useMeetingRoomStore((s) => s.chatMessages);
  const addChatMessage = useMeetingRoomStore((s) => s.addChatMessage);
  const setChatMessages = useMeetingRoomStore((s) => s.setChatMessages);
  const reset = useMeetingRoomStore((s) => s.reset);

  // 화면공유 상태
  const isScreenSharing = useMeetingRoomStore((s) => s.isScreenSharing);
  const screenStream = useMeetingRoomStore((s) => s.screenStream);
  const remoteScreenStreams = useMeetingRoomStore((s) => s.remoteScreenStreams);

  // 녹음 상태
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);

  // Refs
  const roomRef = useRef<Room | null>(null);
  const currentUserIdRef = useRef<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);
  const egressIdRef = useRef<string | null>(null);
  const speechStartTimeRef = useRef<number | null>(null);
  const vadStartTimeRef = useRef<number | null>(null);

  // Web Audio API refs (마이크 게인 조절용)
  const audioContextRef = useRef<AudioContext | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const destinationRef = useRef<MediaStreamAudioDestinationNode | null>(null);

  /**
   * VAD 훅 - 발화 감지
   */
  const vad = useVAD();

  /**
   * LiveKit 연결 상태를 앱 연결 상태로 변환
   */
  const mapConnectionState = useCallback((state: LiveKitConnectionState): ConnectionState => {
    switch (state) {
      case LiveKitConnectionState.Disconnected:
        return 'disconnected';
      case LiveKitConnectionState.Connecting:
        return 'connecting';
      case LiveKitConnectionState.Connected:
        return 'connected';
      case LiveKitConnectionState.Reconnecting:
        return 'reconnecting';
      default:
        return 'disconnected';
    }
  }, []);

  /**
   * LiveKit Participant를 RoomParticipant로 변환
   */
  const mapParticipant = useCallback((participant: Participant, _isLocal = false): RoomParticipant => {
    // identity format: "userId:userName:role"
    const identity = participant.identity;
    const metadata = participant.metadata ? JSON.parse(participant.metadata) : {};

    return {
      userId: identity,
      userName: participant.name || identity,
      role: metadata.role || 'participant',
      audioMuted: !participant.isMicrophoneEnabled,
      isScreenSharing: participant.isScreenShareEnabled,
    };
  }, []);

  /**
   * DataPacket 전송
   */
  const sendDataPacket = useCallback((message: DataMessage, reliable = true) => {
    const room = roomRef.current;
    if (!room || room.state !== LiveKitConnectionState.Connected) {
      logger.warn('[useLiveKit] Cannot send data packet: not connected');
      return;
    }

    const encoder = new TextEncoder();
    const data = encoder.encode(JSON.stringify(message));

    room.localParticipant.publishData(
      data,
      { reliable }
    );
  }, []);

  /**
   * VAD 이벤트 서버 전송
   */
  const sendVADEvent = useCallback((eventType: 'speech_start' | 'speech_end', segment?: VADSegment) => {
    const payload: VADEventPayload = {
      eventType,
      timestamp: new Date().toISOString(),
    };

    if (segment) {
      payload.segmentStartMs = segment.startMs;
      payload.segmentEndMs = segment.endMs;
    } else if (eventType === 'speech_start' && vadStartTimeRef.current) {
      const now = Date.now();
      speechStartTimeRef.current = now;
      payload.segmentStartMs = now - vadStartTimeRef.current;
    }

    sendDataPacket({
      type: 'vad_event',
      payload,
    });
  }, [sendDataPacket]);

  /**
   * 마이크 게인 처리된 스트림 생성
   */
  const createProcessedStream = useCallback(async (
    originalStream: MediaStream,
    gain: number
  ): Promise<MediaStream> => {
    // 기존 노드 정리
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
    }
    if (gainNodeRef.current) {
      gainNodeRef.current.disconnect();
    }

    // AudioContext 생성 또는 재사용
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new AudioContext();
    }

    const audioContext = audioContextRef.current;

    // 노드 생성
    sourceNodeRef.current = audioContext.createMediaStreamSource(originalStream);
    gainNodeRef.current = audioContext.createGain();
    destinationRef.current = audioContext.createMediaStreamDestination();

    // 게인 설정
    gainNodeRef.current.gain.value = gain;

    // 연결
    sourceNodeRef.current.connect(gainNodeRef.current);
    gainNodeRef.current.connect(destinationRef.current);

    return destinationRef.current.stream;
  }, []);

  /**
   * DataPacket 수신 핸들러
   */
  const handleDataReceived = useCallback((
    payload: Uint8Array,
    participant?: RemoteParticipant
  ) => {
    try {
      const decoder = new TextDecoder();
      const message: DataMessage = JSON.parse(decoder.decode(payload));

      switch (message.type) {
        case 'chat_message': {
          const chatPayload = message.payload as ChatMessagePayload;
          if (participant) {
            addChatMessage({
              id: chatPayload.id,
              userId: participant.identity,
              userName: chatPayload.userName || participant.name || participant.identity,
              content: chatPayload.content,
              createdAt: chatPayload.createdAt,
            });
          }
          break;
        }

        case 'force_mute': {
          const forcePayload = message.payload as ForceMutePayload;
          if (forcePayload.targetUserId === currentUserIdRef.current) {
            // 자신이 강제 음소거됨
            logger.log('[useLiveKit] Force muted:', forcePayload.muted);
            setAudioMuted(forcePayload.muted);

            const room = roomRef.current;
            if (room) {
              room.localParticipant.setMicrophoneEnabled(!forcePayload.muted);
            }
          }
          break;
        }

        case 'mute_state': {
          const mutePayload = message.payload as MuteStatePayload;
          if (participant) {
            updateParticipantMute(participant.identity, mutePayload.muted);
          }
          break;
        }

        case 'vad_event': {
          // VAD 이벤트는 서버에서 처리 (로깅만)
          logger.debug('[useLiveKit] VAD event from:', participant?.identity);
          break;
        }
      }
    } catch (err) {
      logger.error('[useLiveKit] Failed to parse data packet:', err);
    }
  }, [addChatMessage, setAudioMuted, updateParticipantMute]);

  /**
   * 원격 트랙 구독 핸들러
   */
  const handleTrackSubscribed = useCallback((
    track: RemoteTrack,
    publication: RemoteTrackPublication,
    participant: RemoteParticipant
  ) => {
    logger.log('[useLiveKit] Track subscribed:', track.kind, 'from:', participant.identity);

    if (track.kind === Track.Kind.Audio) {
      // 오디오 트랙 - MediaStream으로 변환하여 저장
      const mediaStream = new MediaStream([track.mediaStreamTrack]);
      addRemoteStream(participant.identity, mediaStream);
    } else if (track.kind === Track.Kind.Video) {
      // 비디오 트랙 (화면공유)
      if (publication.source === Track.Source.ScreenShare) {
        const screenMediaStream = new MediaStream([track.mediaStreamTrack]);
        addRemoteScreenStream(participant.identity, screenMediaStream);
        updateParticipantScreenSharing(participant.identity, true);
      }
    }
  }, [addRemoteStream, addRemoteScreenStream, updateParticipantScreenSharing]);

  /**
   * 원격 트랙 구독 해제 핸들러
   */
  const handleTrackUnsubscribed = useCallback((
    track: RemoteTrack,
    publication: RemoteTrackPublication,
    participant: RemoteParticipant
  ) => {
    logger.log('[useLiveKit] Track unsubscribed:', track.kind, 'from:', participant.identity);

    if (track.kind === Track.Kind.Audio) {
      removeRemoteStream(participant.identity);
    } else if (track.kind === Track.Kind.Video && publication.source === Track.Source.ScreenShare) {
      removeRemoteScreenStream(participant.identity);
      updateParticipantScreenSharing(participant.identity, false);
    }
  }, [removeRemoteStream, removeRemoteScreenStream, updateParticipantScreenSharing]);

  /**
   * 참여자 입장 핸들러
   */
  const handleParticipantConnected = useCallback((participant: RemoteParticipant) => {
    logger.log('[useLiveKit] Participant connected:', participant.identity);
    addParticipant(mapParticipant(participant));
  }, [addParticipant, mapParticipant]);

  /**
   * 참여자 퇴장 핸들러
   */
  const handleParticipantDisconnected = useCallback((participant: RemoteParticipant) => {
    logger.log('[useLiveKit] Participant disconnected:', participant.identity);
    removeParticipant(participant.identity);
    removeRemoteStream(participant.identity);
    removeRemoteScreenStream(participant.identity);
  }, [removeParticipant, removeRemoteStream, removeRemoteScreenStream]);

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
      logger.log('[useLiveKit] Chat history loaded:', messages.length, 'messages');
    } catch (err) {
      logger.warn('[useLiveKit] Failed to fetch chat history:', err);
    }
  }, [meetingId, setChatMessages]);

  /**
   * LiveKit 토큰 획득
   */
  const getJoinToken = useCallback(async (): Promise<LiveKitTokenResponse> => {
    const response = await api.post<LiveKitTokenResponse>(`/meetings/${meetingId}/join-token`);
    return response.data;
  }, [meetingId]);

  /**
   * 서버 녹음 시작
   */
  const startRecording = useCallback(async () => {
    try {
      const response = await api.post<StartRecordingResponse>(`/meetings/${meetingId}/start-recording`);
      egressIdRef.current = response.data.egressId;
      setIsRecording(true);
      setRecordingError(null);
      logger.log('[useLiveKit] Recording started:', response.data.egressId);
    } catch (err) {
      logger.error('[useLiveKit] Failed to start recording:', err);
      setRecordingError('녹음 시작에 실패했습니다.');
    }
  }, [meetingId]);

  /**
   * 서버 녹음 중지
   */
  const stopRecording = useCallback(async () => {
    if (!isRecording) return;

    try {
      await api.post(`/meetings/${meetingId}/stop-recording`);
      egressIdRef.current = null;
      setIsRecording(false);
      logger.log('[useLiveKit] Recording stopped');
    } catch (err) {
      logger.error('[useLiveKit] Failed to stop recording:', err);
      setRecordingError('녹음 중지에 실패했습니다.');
    }
  }, [meetingId, isRecording]);

  /**
   * 회의 참여
   */
  const joinRoom = useCallback(async (userId: string) => {
    // 이미 연결됨이면 skip
    if (roomRef.current) {
      logger.log('[useLiveKit] joinRoom: already connected, skipping');
      return;
    }

    // 이전 연결 시도 취소 (Strict Mode 대응)
    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    currentUserIdRef.current = userId;
    setConnectionState('connecting');

    try {
      // 1. 채팅 히스토리 로드 및 토큰 획득 병렬 처리
      const [tokenResponse] = await Promise.all([
        getJoinToken(),
        fetchChatHistory(),
      ]);

      // abort 체크: 토큰 획득 후
      if (abortController.signal.aborted) {
        logger.log('[useLiveKit] joinRoom aborted after token fetch');
        setConnectionState('disconnected');
        return;
      }

      logger.log('[useLiveKit] Token received, connecting to:', tokenResponse.wsUrl);

      // 2. LiveKit Room 생성
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });
      // roomRef는 연결 완료 후에 설정 (abort 체크를 위해)

      // ICE 연결 디버깅 (dev 모드에서만)
      if (isDevMode) {
        room.on(RoomEvent.SignalConnected, () => {
          logger.log('[useLiveKit] Signal connected (WebSocket OK)');
        });

        room.on(RoomEvent.MediaDevicesError, (error: Error) => {
          logger.error('[useLiveKit] Media devices error:', error);
        });

        room.on(RoomEvent.ConnectionQualityChanged, (quality, participant) => {
          logger.debug('[useLiveKit] Connection quality:', participant.identity, quality);
        });
      }

      // 3. 이벤트 리스너 등록
      room.on(RoomEvent.ConnectionStateChanged, (state: LiveKitConnectionState) => {
        logger.log('[useLiveKit] Connection state:', state);
        setConnectionState(mapConnectionState(state));
      });

      room.on(RoomEvent.ParticipantConnected, handleParticipantConnected);
      room.on(RoomEvent.ParticipantDisconnected, handleParticipantDisconnected);
      room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
      room.on(RoomEvent.TrackUnsubscribed, handleTrackUnsubscribed);
      room.on(RoomEvent.DataReceived, handleDataReceived);

      room.on(RoomEvent.Disconnected, (reason?: DisconnectReason) => {
        logger.log('[useLiveKit] Disconnected:', reason);
        setConnectionState('disconnected');
      });

      room.on(RoomEvent.Reconnecting, () => {
        logger.log('[useLiveKit] Reconnecting...');
        setConnectionState('reconnecting');
      });

      room.on(RoomEvent.Reconnected, () => {
        logger.log('[useLiveKit] Reconnected');
        setConnectionState('connected');
      });

      // ActiveSpeakersChanged 이벤트로 발화 상태 추적
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers: Participant[]) => {
        // 발화 중인 사용자 업데이트 (UI 표시용)
        logger.debug('[useLiveKit] Active speakers:', speakers.map((s: Participant) => s.identity));
      });

      // 4. 룸 연결
      await room.connect(tokenResponse.wsUrl, tokenResponse.token, {
        // WebRTC 연결 옵션
        rtcConfig: {
          // ICE 서버 설정 (STUN + 선택적 TURN)
          iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' },
          ],
          // 릴레이 모드 강제 (TURN 필요시 'relay'로 변경)
          iceTransportPolicy: 'all',
        },
      });

      // abort 체크: 연결 완료 후 (Strict Mode에서 unmount된 경우)
      if (abortController.signal.aborted) {
        logger.log('[useLiveKit] joinRoom aborted after connect, disconnecting');
        room.disconnect();
        setConnectionState('disconnected');
        return;
      }

      // 연결 성공 후에 roomRef 설정
      roomRef.current = room;
      logger.log('[useLiveKit] Connected to room:', tokenResponse.roomName);

      // 5. 회의 정보 설정
      setMeetingInfo(meetingId, 'in_progress', [], 20);

      // 6. 기존 참여자 목록 업데이트
      const existingParticipants: RoomParticipant[] = [];
      room.remoteParticipants.forEach((participant) => {
        existingParticipants.push(mapParticipant(participant));
      });
      // 자신도 추가
      existingParticipants.push(mapParticipant(room.localParticipant, true));
      setParticipants(existingParticipants);

      // 7. 로컬 오디오 트랙 생성 및 게시
      const currentMicGain = useMeetingRoomStore.getState().micGain;
      const currentDeviceId = useMeetingRoomStore.getState().audioInputDeviceId;

      const tracks = await createLocalTracks({
        audio: currentDeviceId ? { deviceId: currentDeviceId } : true,
        video: false,
      });

      const audioTrack = tracks.find((t: LocalTrack) => t.kind === Track.Kind.Audio) as LocalAudioTrack | undefined;
      if (audioTrack) {
        // 마이크 게인 처리된 스트림 생성
        const originalStream = new MediaStream([audioTrack.mediaStreamTrack]);
        const processedStream = await createProcessedStream(originalStream, currentMicGain);
        setLocalStream(processedStream);

        // VAD 시작
        vadStartTimeRef.current = Date.now();
        await vad.startVAD(processedStream);

        // 트랙 게시
        await room.localParticipant.publishTrack(audioTrack);
        logger.log('[useLiveKit] Audio track published');
      }

      // 8. 연결 완료 시 자동 녹음 시작
      setTimeout(() => {
        startRecording();
      }, 500);

    } catch (err) {
      // abort된 경우 에러 무시 (Strict Mode 정상 동작)
      if (abortController.signal.aborted) {
        logger.log('[useLiveKit] joinRoom aborted, ignoring error');
        return;
      }

      logger.error('[useLiveKit] Failed to join room:', err);

      // 상세 에러 분석 (dev 모드에서)
      if (isDevMode && err instanceof Error) {
        logger.error('[useLiveKit] Error name:', err.name);
        logger.error('[useLiveKit] Error message:', err.message);
        logger.error('[useLiveKit] Error stack:', err.stack);

        // ICE 연결 실패 분석
        if (err.message.includes('pc connection') || err.message.includes('ICE')) {
          logger.error('[useLiveKit] ICE Connection Failed - Possible causes:');
          logger.error('  1. LiveKit RTC ports (7881, 50000-50100) not accessible from client');
          logger.error('  2. NAT/Firewall blocking UDP traffic');
          logger.error('  3. TURN server not configured (required for restrictive networks)');
          logger.error('  4. LiveKit server external IP not properly configured');
        }
      }

      setConnectionState('failed');
      setError(err instanceof Error ? err.message : '회의 참여에 실패했습니다.');
      throw err;
    }
  }, [
    getJoinToken,
    fetchChatHistory,
    mapConnectionState,
    handleParticipantConnected,
    handleParticipantDisconnected,
    handleTrackSubscribed,
    handleTrackUnsubscribed,
    handleDataReceived,
    setMeetingInfo,
    setParticipants,
    mapParticipant,
    createProcessedStream,
    setLocalStream,
    setConnectionState,
    setError,
    startRecording,
    meetingId,
    vad,
  ]);

  /**
   * 회의 퇴장
   */
  const leaveRoom = useCallback(async () => {
    const room = roomRef.current;
    // room이 없으면 이미 정리됨
    if (!room) return;

    // VAD 중지
    vad.stopVAD();

    // 녹음 중지
    await stopRecording();

    // 룸 연결 해제
    room.disconnect();
    roomRef.current = null;

    // Web Audio 정리
    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }
    if (gainNodeRef.current) {
      gainNodeRef.current.disconnect();
      gainNodeRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // 스토어 리셋
    reset();
  }, [vad, stopRecording, reset]);

  /**
   * 오디오 음소거 토글
   */
  const toggleMute = useCallback(() => {
    const currentMuted = useMeetingRoomStore.getState().isAudioMuted;
    const newMuted = !currentMuted;
    setAudioMuted(newMuted);

    const room = roomRef.current;
    if (room) {
      room.localParticipant.setMicrophoneEnabled(!newMuted);

      // 다른 참여자에게 음소거 상태 전송
      sendDataPacket({
        type: 'mute_state',
        payload: { muted: newMuted } as MuteStatePayload,
      });
    }
  }, [setAudioMuted, sendDataPacket]);

  /**
   * 강제 음소거 (Host 전용)
   */
  const forceMute = useCallback((targetUserId: string, muted: boolean) => {
    sendDataPacket({
      type: 'force_mute',
      payload: { targetUserId, muted } as ForceMutePayload,
    });
  }, [sendDataPacket]);

  /**
   * 마이크 입력 장치 변경
   */
  const changeAudioInputDevice = useCallback(async (deviceId: string) => {
    try {
      logger.log('[useLiveKit] Changing audio input device to:', deviceId);

      const room = roomRef.current;
      if (!room) return;

      // 새로운 트랙 생성
      const tracks = await createLocalTracks({
        audio: { deviceId },
        video: false,
      });

      const newAudioTrack = tracks.find((t: LocalTrack) => t.kind === Track.Kind.Audio) as LocalAudioTrack | undefined;
      if (!newAudioTrack) {
        throw new Error('Failed to create audio track');
      }

      // 마이크 게인 처리된 스트림 생성
      const currentMicGain = useMeetingRoomStore.getState().micGain;
      const originalStream = new MediaStream([newAudioTrack.mediaStreamTrack]);
      const processedStream = await createProcessedStream(originalStream, currentMicGain);

      // 현재 음소거 상태 유지
      const currentMuted = useMeetingRoomStore.getState().isAudioMuted;
      if (currentMuted) {
        newAudioTrack.mute();
      }

      // 기존 트랙 교체
      const existingPub = room.localParticipant.getTrackPublication(Track.Source.Microphone);
      if (existingPub?.track) {
        await room.localParticipant.unpublishTrack(existingPub.track as LocalTrack);
      }
      await room.localParticipant.publishTrack(newAudioTrack);

      // VAD 재시작
      vad.stopVAD();
      vadStartTimeRef.current = Date.now();
      await vad.startVAD(processedStream);

      setLocalStream(processedStream);
      setAudioInputDeviceId(deviceId);

      logger.log('[useLiveKit] Audio input device changed successfully');
    } catch (err) {
      logger.error('[useLiveKit] Failed to change audio input device:', err);
      throw err;
    }
  }, [createProcessedStream, setLocalStream, setAudioInputDeviceId, vad]);

  /**
   * 스피커 출력 장치 변경
   */
  const changeAudioOutputDevice = useCallback((deviceId: string) => {
    setAudioOutputDeviceId(deviceId);
    logger.log('[useLiveKit] Audio output device changed to:', deviceId);
  }, [setAudioOutputDeviceId]);

  /**
   * 마이크 gain 변경
   */
  const changeMicGain = useCallback((gain: number) => {
    const clampedGain = Math.max(0, Math.min(2, gain));

    if (gainNodeRef.current) {
      gainNodeRef.current.gain.value = clampedGain;
    }

    setMicGain(clampedGain);
    logger.log('[useLiveKit] Mic gain changed to:', clampedGain);
  }, [setMicGain]);

  /**
   * 원격 참여자 볼륨 변경
   */
  const changeRemoteVolume = useCallback((userId: string, volume: number) => {
    const clampedVolume = Math.max(0, Math.min(2, volume));
    setRemoteVolume(userId, clampedVolume);
    logger.log(`[useLiveKit] Remote volume for ${userId} changed to:`, clampedVolume);
  }, [setRemoteVolume]);

  /**
   * 화면공유 시작
   */
  const startScreenShare = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;

    try {
      await room.localParticipant.setScreenShareEnabled(true);
      const screenPub = room.localParticipant.getTrackPublication(Track.Source.ScreenShare);
      if (screenPub?.track) {
        const stream = new MediaStream([screenPub.track.mediaStreamTrack]);
        setScreenStream(stream);
        setScreenSharing(true);
      }
      logger.log('[useLiveKit] Screen share started');
    } catch (err) {
      logger.error('[useLiveKit] Failed to start screen share:', err);
      throw err;
    }
  }, [setScreenStream, setScreenSharing]);

  /**
   * 화면공유 중지
   */
  const stopScreenShare = useCallback(() => {
    const room = roomRef.current;
    if (!room) return;

    room.localParticipant.setScreenShareEnabled(false);
    setScreenStream(null);
    setScreenSharing(false);
    logger.log('[useLiveKit] Screen share stopped');
  }, [setScreenStream, setScreenSharing]);

  /**
   * 채팅 메시지 전송
   */
  const sendChatMessage = useCallback((content: string) => {
    const room = roomRef.current;
    if (!room) return;

    const messageId = crypto.randomUUID();
    const userName = room.localParticipant.name || room.localParticipant.identity;
    const createdAt = new Date().toISOString();

    // DataPacket으로 전송
    sendDataPacket({
      type: 'chat_message',
      payload: {
        id: messageId,
        content,
        userName,
        createdAt,
      } as ChatMessagePayload,
    });

    // 로컬에도 추가
    addChatMessage({
      id: messageId,
      userId: currentUserIdRef.current,
      userName,
      content,
      createdAt,
    });
  }, [sendDataPacket, addChatMessage]);

  /**
   * VAD 이벤트 처리 (발화 시작/끝 감지)
   */
  useEffect(() => {
    if (vad.isSpeaking && !speechStartTimeRef.current) {
      // 발화 시작
      speechStartTimeRef.current = Date.now();
      sendVADEvent('speech_start');
    } else if (!vad.isSpeaking && speechStartTimeRef.current) {
      // 발화 종료
      const endMs = vadStartTimeRef.current ? Date.now() - vadStartTimeRef.current : 0;
      const startMs = vadStartTimeRef.current && speechStartTimeRef.current
        ? speechStartTimeRef.current - vadStartTimeRef.current
        : 0;

      sendVADEvent('speech_end', { startMs, endMs });
      speechStartTimeRef.current = null;
    }
  }, [vad.isSpeaking, sendVADEvent]);

  /**
   * 회의 중 주기적 토큰 갱신
   */
  useEffect(() => {
    if (connectionState !== 'connected') {
      return;
    }

    logger.log('[useLiveKit] Starting periodic token refresh...');
    ensureValidToken();

    const intervalId = setInterval(() => {
      logger.log('[useLiveKit] Periodic token refresh check...');
      ensureValidToken();
    }, TOKEN_REFRESH_INTERVAL);

    return () => {
      logger.log('[useLiveKit] Stopping periodic token refresh');
      clearInterval(intervalId);
    };
  }, [connectionState]);

  /**
   * cleanup - 컴포넌트 언마운트 시 실행
   * Strict Mode: 진행 중인 연결을 abort하여 2차 마운트에서 정상 연결
   * 실제 페이지 이탈: 연결된 경우 disconnect
   */
  useEffect(() => {
    return () => {
      // 진행 중인 연결 시도 취소 (Strict Mode 대응)
      abortControllerRef.current?.abort();

      const room = roomRef.current;
      // room이 없으면 연결 전이거나 이미 정리됨
      if (!room) return;

      // 실제 페이지 이탈: 연결된 경우 정리
      vad.stopVAD();
      room.disconnect();
      roomRef.current = null;

      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }

      reset();
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
    isRecording,
    recordingError,
    isUploading: false, // 서버 녹음이므로 업로드 상태 없음
    uploadProgress: 100, // 서버 녹음이므로 항상 100%
    audioInputDeviceId,
    audioOutputDeviceId,
    micGain,
    remoteVolumes,
    // 화면공유 상태
    isScreenSharing,
    screenStream,
    remoteScreenStreams,
    // 채팅 상태
    chatMessages,
    // VAD 상태
    isSpeaking: vad.isSpeaking,

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
