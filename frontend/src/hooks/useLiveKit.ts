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
  TrackPublication,
  LocalTrack,
  LocalTrackPublication,
  createLocalTracks,
  LocalAudioTrack,
  DisconnectReason,
  LogLevel,
  setLogLevel,
  ScreenSharePresets,
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
  const updateParticipantScreenSharing = useMeetingRoomStore(
    (s) => s.updateParticipantScreenSharing
  );
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
  const mapParticipant = useCallback(
    (participant: Participant, _isLocal = false): RoomParticipant => {
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
    },
    []
  );

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

    room.localParticipant.publishData(data, { reliable });
  }, []);

  /**
   * VAD 이벤트 서버 전송
   */
  const sendVADEvent = useCallback(
    (eventType: 'speech_start' | 'speech_end', segment?: VADSegment) => {
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
    },
    [sendDataPacket]
  );

  /**
   * 마이크 게인 처리된 스트림 생성
   */
  const createProcessedStream = useCallback(
    async (originalStream: MediaStream, gain: number): Promise<MediaStream> => {
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
    },
    []
  );

  /**
   * DataPacket 수신 핸들러
   */
  const handleDataReceived = useCallback(
    (payload: Uint8Array, participant?: RemoteParticipant) => {
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
    },
    [addChatMessage, setAudioMuted, updateParticipantMute]
  );

  /**
   * 원격 트랙 구독 핸들러
   */
  const handleTrackSubscribed = useCallback(
    (track: RemoteTrack, publication: RemoteTrackPublication, participant: RemoteParticipant) => {
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
    },
    [addRemoteStream, addRemoteScreenStream, updateParticipantScreenSharing]
  );

  /**
   * 원격 트랙 구독 해제 핸들러
   */
  const handleTrackUnsubscribed = useCallback(
    (track: RemoteTrack, publication: RemoteTrackPublication, participant: RemoteParticipant) => {
      logger.log('[useLiveKit] Track unsubscribed:', track.kind, 'from:', participant.identity);

      if (track.kind === Track.Kind.Audio) {
        removeRemoteStream(participant.identity);
      } else if (
        track.kind === Track.Kind.Video &&
        publication.source === Track.Source.ScreenShare
      ) {
        removeRemoteScreenStream(participant.identity);
        updateParticipantScreenSharing(participant.identity, false);
      }
    },
    [removeRemoteStream, removeRemoteScreenStream, updateParticipantScreenSharing]
  );

  /**
   * 참여자 입장 핸들러
   */
  const handleParticipantConnected = useCallback(
    (participant: RemoteParticipant) => {
      logger.log('[useLiveKit] Participant connected:', participant.identity);
      addParticipant(mapParticipant(participant));
      // LiveKit SDK의 자동 구독 메커니즘에 의존 (수동 구독 제거)
    },
    [addParticipant, mapParticipant]
  );

  /**
   * 참여자 퇴장 핸들러
   */
  const handleParticipantDisconnected = useCallback(
    (participant: RemoteParticipant) => {
      logger.log('[useLiveKit] Participant disconnected:', participant.identity);

      // LiveKit SDK가 자동으로 트랙을 정리하므로 우리는 스토어 상태만 정리
      // detach()나 stop()을 호출하면 SDK 내부 상태가 꼬여서 재접속 시 문제 발생
      removeParticipant(participant.identity);
      removeRemoteStream(participant.identity);
      removeRemoteScreenStream(participant.identity);
    },
    [removeParticipant, removeRemoteStream, removeRemoteScreenStream]
  );

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
      const response = await api.post<StartRecordingResponse>(
        `/meetings/${meetingId}/start-recording`
      );
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
   * Room 이벤트 핸들러 등록
   */
  const setupRoomEventListeners = useCallback(
    (room: Room) => {
      // 디버깅 이벤트 (dev 모드에서만)
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

      // 연결 상태 변경
      room.on(RoomEvent.ConnectionStateChanged, (state: LiveKitConnectionState) => {
        logger.log('[useLiveKit] Connection state:', state);
        setConnectionState(mapConnectionState(state));
      });

      // 참여자 이벤트
      room.on(RoomEvent.ParticipantConnected, handleParticipantConnected);
      room.on(RoomEvent.ParticipantDisconnected, handleParticipantDisconnected);

      // 트랙 이벤트
      room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
      room.on(RoomEvent.TrackUnsubscribed, handleTrackUnsubscribed);

      // 트랙 발행 (초기 mute 상태 동기화)
      room.on(
        RoomEvent.TrackPublished,
        (publication: RemoteTrackPublication, participant: RemoteParticipant) => {
          logger.log(
            '[useLiveKit] Track published:',
            publication.kind,
            'from:',
            participant.identity
          );
          if (publication.kind === Track.Kind.Audio) {
            updateParticipantMute(participant.identity, publication.isMuted);
          }
        }
      );

      // 음소거 상태 변경
      room.on(RoomEvent.TrackMuted, (publication: TrackPublication, participant: Participant) => {
        if (publication.kind === Track.Kind.Audio) {
          updateParticipantMute(participant.identity, true);
        }
      });

      room.on(RoomEvent.TrackUnmuted, (publication: TrackPublication, participant: Participant) => {
        if (publication.kind === Track.Kind.Audio) {
          updateParticipantMute(participant.identity, false);
        }
      });

      // 재연결 이벤트
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

      // 로컬 화면공유 트랙 해제 (브라우저 "공유 중지" 버튼 등)
      room.on(
        RoomEvent.LocalTrackUnpublished,
        (publication: LocalTrackPublication) => {
          if (publication.source === Track.Source.ScreenShare) {
            logger.log('[useLiveKit] Local screen share track unpublished');
            setScreenStream(null);
            setScreenSharing(false);
          }
        }
      );

      // 데이터 수신
      room.on(RoomEvent.DataReceived, handleDataReceived);
    },
    [
      mapConnectionState,
      handleParticipantConnected,
      handleParticipantDisconnected,
      handleTrackSubscribed,
      handleTrackUnsubscribed,
      handleDataReceived,
      updateParticipantMute,
      setConnectionState,
      setScreenStream,
      setScreenSharing,
    ]
  );

  /**
   * 로컬 오디오 트랙 생성 및 게시
   */
  const setupLocalAudioTrack = useCallback(
    async (room: Room) => {
      const currentMicGain = useMeetingRoomStore.getState().micGain;
      const currentDeviceId = useMeetingRoomStore.getState().audioInputDeviceId;

      // 기존 Web Audio 리소스 정리 (재접속 시 중요)
      if (sourceNodeRef.current) {
        sourceNodeRef.current.disconnect();
        sourceNodeRef.current = null;
      }
      if (gainNodeRef.current) {
        gainNodeRef.current.disconnect();
        gainNodeRef.current = null;
      }
      if (destinationRef.current) {
        destinationRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        await audioContextRef.current.close();
        audioContextRef.current = null;
      }

      // 트랙 생성
      const tracks = await createLocalTracks({
        audio: currentDeviceId ? { deviceId: currentDeviceId } : true,
        video: false,
      });

      const audioTrack = tracks.find((t: LocalTrack) => t.kind === Track.Kind.Audio) as
        | LocalAudioTrack
        | undefined;
      if (!audioTrack) {
        throw new Error('Failed to create audio track');
      }

      // 트랙 상태 확인
      if (audioTrack.mediaStreamTrack.readyState === 'ended') {
        throw new Error('Created audio track is already ended');
      }

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
    },
    [createProcessedStream, setLocalStream, vad]
  );

  /**
   * 회의 참여
   */
  const joinRoom = useCallback(
    async (userId: string) => {
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
        const [tokenResponse] = await Promise.all([getJoinToken(), fetchChatHistory()]);

        // abort 체크: 토큰 획득 후
        if (abortController.signal.aborted) {
          logger.log('[useLiveKit] joinRoom aborted after token fetch');
          setConnectionState('disconnected');
          return;
        }

        logger.log('[useLiveKit] Token received, connecting to:', tokenResponse.wsUrl);

        // 2. LiveKit Room 생성 및 이벤트 리스너 등록
        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
          stopLocalTrackOnUnpublish: true,
        });

        setupRoomEventListeners(room);

        // 3. 룸 연결
        await room.connect(tokenResponse.wsUrl, tokenResponse.token);

        // abort 체크: 연결 완료 후
        if (abortController.signal.aborted) {
          logger.log('[useLiveKit] joinRoom aborted after connect, disconnecting');
          room.disconnect();
          setConnectionState('disconnected');
          return;
        }

        roomRef.current = room;
        logger.log('[useLiveKit] Connected to room:', tokenResponse.roomName);

        // 4. 회의 정보 설정
        setMeetingInfo(meetingId, 'in_progress');

        // 5. 기존 참여자 목록 업데이트
        const existingParticipants: RoomParticipant[] = [];
        room.remoteParticipants.forEach((participant) => {
          existingParticipants.push(mapParticipant(participant));
        });
        existingParticipants.push(mapParticipant(room.localParticipant, true));
        setParticipants(existingParticipants);

        // 6. 로컬 오디오 트랙 생성 및 게시 (마이크 없어도 참여 가능)
        try {
          await setupLocalAudioTrack(room);
        } catch (audioErr) {
          logger.warn('[useLiveKit] 오디오 트랙 생성 실패 (마이크 없이 참여):', audioErr);
          setAudioMuted(true);
        }

        // 7. 자동 녹음 시작
        setTimeout(() => {
          startRecording();
        }, 500);
      } catch (err) {
        // abort된 경우 에러 무시
        if (abortController.signal.aborted) {
          logger.log('[useLiveKit] joinRoom aborted, ignoring error');
          return;
        }

        logger.error('[useLiveKit] Failed to join room:', err);
        setConnectionState('failed');
        setError('회의 연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
        throw err;
      }
    },
    [
      getJoinToken,
      fetchChatHistory,
      setupRoomEventListeners,
      setMeetingInfo,
      setParticipants,
      mapParticipant,
      setupLocalAudioTrack,
      setConnectionState,
      setError,
      startRecording,
      meetingId,
    ]
  );

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
  const toggleMute = useCallback(async () => {
    const currentMuted = useMeetingRoomStore.getState().isAudioMuted;
    const newMuted = !currentMuted;
    setAudioMuted(newMuted);

    const room = roomRef.current;
    if (room) {
      await room.localParticipant.setMicrophoneEnabled(!newMuted);

      // 음소거 해제 시 sourceNode 재연결 (Web Audio 그래프 복구)
      if (!newMuted && audioContextRef.current && gainNodeRef.current) {
        // LiveKit 트랙에서 새 MediaStream 생성
        const audioPublication = room.localParticipant.audioTrackPublications.values().next().value;
        if (audioPublication?.track?.mediaStreamTrack) {
          const freshStream = new MediaStream([audioPublication.track.mediaStreamTrack]);

          // 기존 sourceNode 해제 후 재연결
          sourceNodeRef.current?.disconnect();
          sourceNodeRef.current = audioContextRef.current.createMediaStreamSource(freshStream);
          sourceNodeRef.current.connect(gainNodeRef.current);
          logger.log('[useLiveKit] sourceNode reconnected after unmute');
        }
      }

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
  const forceMute = useCallback(
    (targetUserId: string, muted: boolean) => {
      sendDataPacket({
        type: 'force_mute',
        payload: { targetUserId, muted } as ForceMutePayload,
      });
    },
    [sendDataPacket]
  );

  /**
   * 마이크 입력 장치 변경
   */
  const changeAudioInputDevice = useCallback(
    async (deviceId: string) => {
      try {
        logger.log('[useLiveKit] Changing audio input device to:', deviceId);

        const room = roomRef.current;
        if (!room) return;

        // 새로운 트랙 생성
        const tracks = await createLocalTracks({
          audio: { deviceId },
          video: false,
        });

        const newAudioTrack = tracks.find((t: LocalTrack) => t.kind === Track.Kind.Audio) as
          | LocalAudioTrack
          | undefined;
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
    },
    [createProcessedStream, setLocalStream, setAudioInputDeviceId, vad]
  );

  /**
   * 스피커 출력 장치 변경
   */
  const changeAudioOutputDevice = useCallback(
    (deviceId: string) => {
      setAudioOutputDeviceId(deviceId);
      logger.log('[useLiveKit] Audio output device changed to:', deviceId);
    },
    [setAudioOutputDeviceId]
  );

  /**
   * 마이크 gain 변경
   */
  const changeMicGain = useCallback(
    (gain: number) => {
      const clampedGain = Math.max(0, Math.min(2, gain));

      if (gainNodeRef.current) {
        gainNodeRef.current.gain.value = clampedGain;
      }

      setMicGain(clampedGain);
      logger.log('[useLiveKit] Mic gain changed to:', clampedGain);
    },
    [setMicGain]
  );

  /**
   * 원격 참여자 볼륨 변경
   */
  const changeRemoteVolume = useCallback(
    (userId: string, volume: number) => {
      const clampedVolume = Math.max(0, Math.min(2, volume));
      setRemoteVolume(userId, clampedVolume);
      logger.log(`[useLiveKit] Remote volume for ${userId} changed to:`, clampedVolume);
    },
    [setRemoteVolume]
  );

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
   * 화면공유 시작
   */
  const startScreenShare = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;

    // 룸당 화면공유 1명 제한
    const currentRemoteScreenStreams = useMeetingRoomStore.getState().remoteScreenStreams;
    if (currentRemoteScreenStreams.size > 0) {
      throw new Error('SCREEN_SHARE_LIMIT');
    }

    try {
      // setScreenShareEnabled의 반환값(LocalTrackPublication)을 직접 사용하여
      // getTrackPublication() 호출 시 발생하는 race condition 제거
      const publication = await room.localParticipant.setScreenShareEnabled(
        true,
        // ScreenShareCaptureOptions: HD 해상도
        {
          audio: false,
          resolution: { width: 1920, height: 1080, frameRate: 15 },
        },
        // TrackPublishOptions: 인코딩 품질
        {
          screenShareEncoding: ScreenSharePresets.h1080fps15.encoding,
          videoCodec: 'vp9',
        }
      );

      if (publication?.track) {
        const stream = new MediaStream([publication.track.mediaStreamTrack]);
        setScreenStream(stream);
        setScreenSharing(true);

        // 브라우저 "공유 중지" 버튼 클릭 시 상태 정리
        publication.track.mediaStreamTrack.addEventListener('ended', () => {
          logger.log('[useLiveKit] Screen share track ended (browser stop button)');
          stopScreenShare();
        });
      } else {
        logger.warn('[useLiveKit] Screen share publication returned undefined (user cancelled?)');
      }
      logger.log('[useLiveKit] Screen share started');
    } catch (err) {
      logger.error('[useLiveKit] Failed to start screen share:', err);
      throw err;
    }
  }, [setScreenStream, setScreenSharing, stopScreenShare]);

  /**
   * 채팅 메시지 전송
   */
  const sendChatMessage = useCallback(
    (content: string) => {
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
    },
    [sendDataPacket, addChatMessage]
  );

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
      const startMs =
        vadStartTimeRef.current && speechStartTimeRef.current
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
