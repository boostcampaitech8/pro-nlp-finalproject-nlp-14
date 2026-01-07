/**
 * 회의실 메인 컴포넌트
 */

import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWebRTC } from '@/hooks/useWebRTC';
import { useMultiAudioLevels } from '@/hooks/useAudioLevel';
import { AudioControls } from './AudioControls';
import { ParticipantList } from './ParticipantList';
import { ScreenShareView } from './ScreenShareView';

interface MeetingRoomProps {
  meetingId: string;
  userId: string;
  meetingTitle: string;
  onLeave?: () => void;
}

/**
 * 원격 오디오 재생 컴포넌트
 * - HTMLAudioElement를 사용하여 안정적인 오디오 재생
 * - GainNode를 통한 볼륨 조절 지원 (0-2 범위)
 * - setSinkId를 통한 출력 장치 선택 지원
 */
function RemoteAudio({
  stream,
  odId,
  outputDeviceId,
  volume,
}: {
  stream: MediaStream;
  odId: string;
  outputDeviceId: string | null;
  volume: number;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const isSetupRef = useRef(false);

  // audio 요소에 스트림 연결 및 Web Audio API로 볼륨 조절
  useEffect(() => {
    if (!stream || !audioRef.current) return;

    // 이미 설정되어 있으면 skip
    if (isSetupRef.current && audioContextRef.current) {
      return;
    }

    const audioElement = audioRef.current;
    console.log('[RemoteAudio] Setting up audio for:', odId, 'tracks:', stream.getAudioTracks().length);

    // 스트림의 오디오 트랙 확인
    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) {
      console.warn('[RemoteAudio] No audio tracks in stream for:', odId);
      return;
    }

    audioTracks.forEach((track, i) => {
      console.log(`[RemoteAudio] Track ${i}: enabled=${track.enabled}, muted=${track.muted}, readyState=${track.readyState}`);
    });

    // audio 요소에 스트림 연결
    audioElement.srcObject = stream;

    // Web Audio API로 볼륨 조절 (GainNode 사용)
    try {
      const audioContext = new AudioContext();

      // AudioContext가 suspended 상태면 resume
      if (audioContext.state === 'suspended') {
        console.log('[RemoteAudio] Resuming suspended AudioContext');
        audioContext.resume().catch((err) => {
          console.error('[RemoteAudio] Failed to resume AudioContext:', err);
        });
      }

      const source = audioContext.createMediaStreamSource(stream);
      const gainNode = audioContext.createGain();

      // 초기 볼륨 설정
      gainNode.gain.value = 1.0;

      // 연결: source -> gainNode -> destination
      source.connect(gainNode);
      gainNode.connect(audioContext.destination);

      audioContextRef.current = audioContext;
      gainNodeRef.current = gainNode;
      sourceRef.current = source;

      // audio 요소는 음소거 (Web Audio API가 실제 출력 담당)
      audioElement.muted = true;
      audioElement.volume = 0;

      isSetupRef.current = true;
      console.log('[RemoteAudio] Audio setup complete for:', odId);
    } catch (err) {
      console.error('[RemoteAudio] Failed to setup Web Audio API, using audio element:', err);
      // Web Audio API 실패시 audio 요소로 재생
      audioElement.muted = false;
      audioElement.volume = 1.0;
      isSetupRef.current = true;
    }

    // 재생 시작
    audioElement.play().catch((err) => {
      console.error('[RemoteAudio] Failed to play audio:', err);
    });

    return () => {
      console.log('[RemoteAudio] Cleaning up audio for:', odId);
      isSetupRef.current = false;

      if (sourceRef.current) {
        sourceRef.current.disconnect();
        sourceRef.current = null;
      }
      if (gainNodeRef.current) {
        gainNodeRef.current.disconnect();
        gainNodeRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }

      audioElement.srcObject = null;
    };
  }, [stream, odId]);

  // 볼륨 변경
  useEffect(() => {
    if (gainNodeRef.current) {
      gainNodeRef.current.gain.value = volume;
      console.log('[RemoteAudio] Volume changed for', odId, ':', volume);
    } else if (audioRef.current && !audioRef.current.muted) {
      // Web Audio API 미사용 시 audio 요소 볼륨 직접 조절
      audioRef.current.volume = Math.min(1, volume);
    }
  }, [volume, odId]);

  // 출력 장치 변경 (setSinkId 지원 브라우저만)
  useEffect(() => {
    if (audioRef.current && outputDeviceId) {
      const audioElement = audioRef.current as HTMLAudioElement & {
        setSinkId?: (sinkId: string) => Promise<void>;
      };
      if (audioElement.setSinkId) {
        audioElement.setSinkId(outputDeviceId).catch((err) => {
          console.error('[RemoteAudio] Failed to set output device:', err);
        });
      }
    }
  }, [outputDeviceId]);

  return <audio ref={audioRef} autoPlay playsInline style={{ display: 'none' }} />;
}

export function MeetingRoom({ meetingId, userId, meetingTitle, onLeave }: MeetingRoomProps) {
  const navigate = useNavigate();
  const hasJoinedRef = useRef(false);

  const {
    connectionState,
    participants,
    localStream,
    remoteStreams,
    isAudioMuted,
    error,
    isRecording,
    isUploading,
    audioInputDeviceId,
    audioOutputDeviceId,
    micGain,
    remoteVolumes,
    // 화면공유
    isScreenSharing,
    screenStream,
    remoteScreenStreams,
    joinRoom,
    leaveRoom,
    toggleMute,
    changeAudioInputDevice,
    changeAudioOutputDevice,
    changeMicGain,
    changeRemoteVolume,
    // 화면공유
    startScreenShare,
    stopScreenShare,
  } = useWebRTC(meetingId);

  // 오디오 레벨 분석 (발화 인디케이터용)
  const audioLevels = useMultiAudioLevels(remoteStreams, localStream, userId);

  // 화면공유 토글
  const handleToggleScreenShare = useCallback(() => {
    if (isScreenSharing) {
      stopScreenShare();
    } else {
      startScreenShare().catch((err) => {
        console.error('Failed to start screen share:', err);
      });
    }
  }, [isScreenSharing, startScreenShare, stopScreenShare]);

  // 참여자 이름 조회
  const getUserName = useCallback((participantUserId: string) => {
    const participant = participants.get(participantUserId);
    return participant?.userName ?? 'Unknown';
  }, [participants]);

  // 화면공유 활성화 여부 (로컬 또는 원격 화면공유가 있는지)
  const hasActiveScreenShare = screenStream !== null || remoteScreenStreams.size > 0;

  // 회의 참여
  useEffect(() => {
    if (!hasJoinedRef.current) {
      hasJoinedRef.current = true;
      joinRoom(userId).catch((err) => {
        console.error('Failed to join room:', err);
      });
    }
  }, [joinRoom, userId]);

  // 회의 퇴장
  const handleLeave = () => {
    leaveRoom();
    if (onLeave) {
      onLeave();
    } else {
      navigate(`/meetings/${meetingId}`);
    }
  };

  // 연결 상태에 따른 UI
  if (connectionState === 'connecting') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-white text-lg">회의에 연결 중...</p>
        </div>
      </div>
    );
  }

  // 연결 실패일 때만 에러 화면 표시 (녹음 에러는 별도 처리)
  if (connectionState === 'failed') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-6xl mb-4">!</div>
          <p className="text-white text-lg mb-2">연결 실패</p>
          <p className="text-gray-400 mb-4">{error || '알 수 없는 오류가 발생했습니다.'}</p>
          <button
            onClick={handleLeave}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            돌아가기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* 원격 오디오 재생 (숨김) */}
      {Array.from(remoteStreams.entries()).map(([odId, stream]) => (
        <RemoteAudio
          key={odId}
          stream={stream}
          odId={odId}
          outputDeviceId={audioOutputDeviceId}
          volume={remoteVolumes.get(odId) ?? 1.0}
        />
      ))}

      {/* 헤더 */}
      <header className="bg-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">{meetingTitle}</h1>
          <p className="text-sm text-gray-400">
            {connectionState === 'connected' ? '연결됨' : '연결 중...'}
          </p>
        </div>
        <button
          onClick={handleLeave}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
        >
          회의 나가기
        </button>
      </header>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 flex">
        {/* 중앙 영역 - 화면공유 또는 오디오 시각화 */}
        <div className="flex-1 flex items-center justify-center p-8">
          {hasActiveScreenShare ? (
            <ScreenShareView
              localScreenStream={screenStream}
              remoteScreenStreams={remoteScreenStreams}
              getUserName={getUserName}
              currentUserId={userId}
            />
          ) : (
            <div className="text-center">
              <div className="w-32 h-32 rounded-full bg-gray-700 flex items-center justify-center mx-auto mb-4">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className={`h-16 w-16 ${isAudioMuted ? 'text-gray-500' : 'text-green-400'}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                </svg>
              </div>
              <p className="text-gray-300 text-lg">음성 회의 진행 중</p>
              <p className="text-gray-500 text-sm mt-1">
                {participants.size}명 참여 중
              </p>
            </div>
          )}
        </div>

        {/* 사이드바 - 참여자 목록 */}
        <aside className="w-80 bg-gray-850 p-4 border-l border-gray-700">
          <ParticipantList
            participants={participants}
            currentUserId={userId}
            audioLevels={audioLevels}
            localMuteState={isAudioMuted}
            remoteVolumes={remoteVolumes}
            onVolumeChange={changeRemoteVolume}
          />
        </aside>
      </main>

      {/* 하단 컨트롤 */}
      <footer className="bg-gray-800 px-6 py-4 flex items-center justify-center gap-4">
        <AudioControls
          isAudioMuted={isAudioMuted}
          onToggleMute={toggleMute}
          disabled={connectionState !== 'connected'}
          audioInputDeviceId={audioInputDeviceId}
          audioOutputDeviceId={audioOutputDeviceId}
          onAudioInputChange={changeAudioInputDevice}
          onAudioOutputChange={changeAudioOutputDevice}
          micGain={micGain}
          onMicGainChange={changeMicGain}
          isScreenSharing={isScreenSharing}
          onToggleScreenShare={handleToggleScreenShare}
        />

        {/* 녹음 상태 인디케이터 (자동 녹음) */}
        {isRecording && (
          <div className="flex items-center gap-2 px-3 py-1 bg-red-900/50 rounded-full">
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
            <span className="text-red-400 text-sm">녹음 중</span>
          </div>
        )}
        {isUploading && (
          <div className="flex items-center gap-2 px-3 py-1 bg-blue-900/50 rounded-full">
            <svg className="animate-spin h-4 w-4 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-blue-400 text-sm">저장 중...</span>
          </div>
        )}
      </footer>
    </div>
  );
}
