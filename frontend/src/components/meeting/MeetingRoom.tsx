/**
 * 회의실 메인 컴포넌트
 */

import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWebRTC } from '@/hooks/useWebRTC';
import { useMultiAudioLevels } from '@/hooks/useAudioLevel';
import { AudioControls } from './AudioControls';
import { ParticipantList } from './ParticipantList';

interface MeetingRoomProps {
  meetingId: string;
  userId: string;
  meetingTitle: string;
  onLeave?: () => void;
}

/**
 * 원격 오디오 재생 컴포넌트
 */
function RemoteAudio({ stream, odId }: { stream: MediaStream; odId: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (audioRef.current && stream) {
      console.log('[RemoteAudio] Attaching stream for:', odId);
      audioRef.current.srcObject = stream;
      audioRef.current.play().catch((e) => {
        console.error('[RemoteAudio] Failed to play:', e);
      });
    }
  }, [stream, odId]);

  return <audio ref={audioRef} autoPlay playsInline />;
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
    joinRoom,
    leaveRoom,
    toggleMute,
  } = useWebRTC(meetingId);

  // 오디오 레벨 분석 (발화 인디케이터용)
  const audioLevels = useMultiAudioLevels(remoteStreams, localStream, userId);

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
        <RemoteAudio key={odId} stream={stream} odId={odId} />
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
        {/* 중앙 영역 - 오디오 시각화 (추후 확장) */}
        <div className="flex-1 flex items-center justify-center p-8">
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
        </div>

        {/* 사이드바 - 참여자 목록 */}
        <aside className="w-80 bg-gray-850 p-4 border-l border-gray-700">
          <ParticipantList
            participants={participants}
            currentUserId={userId}
            audioLevels={audioLevels}
          />
        </aside>
      </main>

      {/* 하단 컨트롤 */}
      <footer className="bg-gray-800 px-6 py-4 flex items-center justify-center gap-4">
        <AudioControls
          isAudioMuted={isAudioMuted}
          onToggleMute={toggleMute}
          disabled={connectionState !== 'connected'}
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
