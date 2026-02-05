/**
 * 회의실 메인 컴포넌트
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLiveKit } from '@/hooks/useLiveKit';
import { useMultiAudioLevels } from '@/hooks/useAudioLevel';
import { useMeetingTopics } from '@/hooks/useMeetingTopics';
import { AudioControls } from './AudioControls';
import { ParticipantList } from './ParticipantList';
import { ScreenShareView } from './ScreenShareView';
import { ChatPanel } from './ChatPanel';
import { RemoteAudio } from './RemoteAudio';
import { TopicSidebar } from './TopicSidebar';
import logger from '@/utils/logger';

interface MeetingRoomProps {
  meetingId: string;
  userId: string;
  meetingTitle: string;
  onLeave?: () => void;
}

export function MeetingRoom({ meetingId, userId, meetingTitle, onLeave }: MeetingRoomProps) {
  const navigate = useNavigate();
  const [isLeaving, setIsLeaving] = useState(false);
  const [showParticipants, setShowParticipants] = useState(true);
  const [showChat, setShowChat] = useState(true);
  const [showRecordingNotice, setShowRecordingNotice] = useState(false);
  const [showScreenShareLimitNotice, setShowScreenShareLimitNotice] = useState(false);
  const prevRecordingRef = useRef(false);

  // MIT 에이전트 대기 관련 상태
  const [isInitialJoin, setIsInitialJoin] = useState(true);
  const [agentWaitTimedOut, setAgentWaitTimedOut] = useState(false);

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
    remoteVolumes,
    // 화면공유
    isScreenSharing,
    screenStream,
    remoteScreenStreams,
    joinRoom,
    leaveRoom,
    toggleMute,
    forceMute,
    changeAudioInputDevice,
    changeAudioOutputDevice,
    changeRemoteVolume,
    // 화면공유
    startScreenShare,
    stopScreenShare,
    getRemoteScreenTrack,
    // 채팅
    chatMessages,
    sendChatMessage,
  } = useLiveKit(meetingId);

  // MIT 에이전트 참여 여부 확인
  const MIT_AGENT_IDENTITY = `mit-agent-meeting-${meetingId}`;
  const isAgentPresent = participants.has(MIT_AGENT_IDENTITY);
  const shouldShowLoading = isInitialJoin && connectionState !== 'failed';

  // 현재 사용자가 Host인지 확인
  const currentParticipant = participants.get(userId);
  const isHost = currentParticipant?.role === 'host';

  // 오디오 레벨 분석 (발화 인디케이터용)
  const audioLevels = useMultiAudioLevels(remoteStreams, localStream, userId);

  // 실시간 토픽 스트리밍 - 연결됐을 때만 활성화
  const {
    topics,
    isL1Running,
    pendingChunks,
  } = useMeetingTopics(meetingId, {
    enabled: connectionState === 'connected',
  });

  // 화면공유 토글
  const handleToggleScreenShare = useCallback(() => {
    if (isScreenSharing) {
      stopScreenShare();
    } else {
      startScreenShare().catch((err) => {
        if (err?.message === 'SCREEN_SHARE_LIMIT') {
          setShowScreenShareLimitNotice(true);
          setTimeout(() => setShowScreenShareLimitNotice(false), 3000);
        } else {
          logger.error('Failed to start screen share:', err);
        }
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

  // 회의 참여 (joinRoom 내부에서 중복 호출 방지)
  useEffect(() => {
    joinRoom(userId).catch((err) => {
      logger.error('Failed to join room:', err);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  // MIT 에이전트 대기 타임아웃 (초기 접속 시에만)
  useEffect(() => {
    if (!isInitialJoin) return;
    if (connectionState !== 'connected') return;

    if (isAgentPresent) {
      setIsInitialJoin(false);
      return;
    }

    const timer = setTimeout(() => {
      logger.warn('[MeetingRoom] MIT agent wait timeout - entering meeting without agent');
      setAgentWaitTimedOut(true);
      setIsInitialJoin(false);
    }, 20_000);

    return () => clearTimeout(timer);
  }, [isInitialJoin, connectionState, isAgentPresent]);

  // 녹음 시작 알림 (녹음이 false -> true로 변경될 때만)
  useEffect(() => {
    if (isRecording && !prevRecordingRef.current) {
      setShowRecordingNotice(true);
      const timer = setTimeout(() => setShowRecordingNotice(false), 5000);
      return () => clearTimeout(timer);
    }
    prevRecordingRef.current = isRecording;
  }, [isRecording]);

  // 회의 퇴장
  const handleLeave = async () => {
    if (isLeaving) return;
    setIsLeaving(true);

    try {
      // 녹음 업로드가 완료될 때까지 대기
      await leaveRoom();
    } finally {
      if (onLeave) {
        onLeave();
      } else {
        navigate(`/dashboard/meetings/${meetingId}`);
      }
    }
  };

  // 연결 상태에 따른 UI (에이전트 대기 포함)
  if (shouldShowLoading) {
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
    <div className="h-screen bg-gray-900 flex flex-col overflow-hidden">
      {/* MIT 에이전트 연결 실패 경고 */}
      {agentWaitTimedOut && !isAgentPresent && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50
                        bg-yellow-600 text-white px-4 py-2 rounded-lg shadow-lg
                        flex items-center gap-2 animate-fade-in">
          <span className="text-yellow-200">&#9888;</span>
          서버가 불안정합니다. 회의를 다시 시작해주세요.
        </div>
      )}

      {/* 녹음 시작 알림 토스트 */}
      {showRecordingNotice && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50
                        bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg
                        flex items-center gap-2 animate-fade-in">
          <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
          녹음이 시작되었습니다
        </div>
      )}

      {/* 화면공유 제한 알림 토스트 */}
      {showScreenShareLimitNotice && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50
                        bg-yellow-600 text-white px-4 py-2 rounded-lg shadow-lg
                        flex items-center gap-2 animate-fade-in">
          <span className="text-yellow-200">&#9888;</span>
          다른 참여자가 이미 화면을 공유하고 있습니다
        </div>
      )}

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
          disabled={isLeaving}
          className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {isLeaving && (
            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )}
          {isLeaving ? '저장 중...' : '회의 나가기'}
        </button>
      </header>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 min-h-0 flex">
        {/* 왼쪽 토픽 사이드바 */}
        <TopicSidebar
          topics={topics}
          isL1Running={isL1Running}
          pendingChunks={pendingChunks}
        />

        {/* 중앙 영역 - 화면공유 또는 오디오 시각화 */}
        <div className="flex-1 min-h-0 flex items-center justify-center p-8 relative">

          {hasActiveScreenShare ? (
            <ScreenShareView
              localScreenStream={screenStream}
              remoteScreenStreams={remoteScreenStreams}
              getUserName={getUserName}
              currentUserId={userId}
              getRemoteScreenTrack={getRemoteScreenTrack}
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

        {/* 사이드바 - 참여자 목록 + 채팅 */}
        <aside className="w-80 bg-gray-850 border-l border-gray-700 flex flex-col">
          {/* 참여자 목록 헤더 - 항상 표시 */}
          <div className="border-b border-gray-700">
            <button
              onClick={() => setShowParticipants(!showParticipants)}
              className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
            >
              <span className="text-white font-medium flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
                참여자 ({participants.size})
              </span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className={`h-4 w-4 text-gray-400 transition-transform ${showParticipants ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {/* 참여자 목록 컨텐츠 - 토글로 표시/숨김 */}
            {showParticipants && (
              <div className="p-4 pt-0">
                <ParticipantList
                  participants={participants}
                  currentUserId={userId}
                  audioLevels={audioLevels}
                  localMuteState={isAudioMuted}
                  remoteVolumes={remoteVolumes}
                  onVolumeChange={changeRemoteVolume}
                  isHost={isHost}
                  onForceMute={forceMute}
                />
              </div>
            )}
          </div>
          {/* 채팅 */}
          <div className="flex-1 min-h-0 flex flex-col">
            {/* 채팅 헤더 - 항상 표시 */}
            <button
              onClick={() => setShowChat(!showChat)}
              className="px-4 py-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors border-b border-gray-700"
            >
              <span className="text-white font-medium flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                채팅
              </span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className={`h-4 w-4 text-gray-400 transition-transform ${showChat ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {/* 채팅 컨텐츠 - 토글로 표시/숨김 */}
            {showChat && (
              <div className="flex-1 min-h-0">
                <ChatPanel
                  messages={chatMessages}
                  onSendMessage={sendChatMessage}
                  disabled={connectionState !== 'connected'}
                  currentUserId={userId}
                  hideHeader
                />
              </div>
            )}
          </div>
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
