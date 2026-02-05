/**
 * 화면공유 표시 컴포넌트
 * 여러 명의 화면공유를 그리드 레이아웃으로 표시
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { RemoteTrack } from 'livekit-client';

interface ScreenShareViewProps {
  // 로컬 화면공유
  localScreenStream: MediaStream | null;
  // 원격 화면공유 (userId -> stream)
  remoteScreenStreams: Map<string, MediaStream>;
  // 참여자 이름 조회 함수
  getUserName: (userId: string) => string;
  // 현재 사용자 ID
  currentUserId: string;
  // 원격 화면공유 RemoteTrack 조회 (attach/detach용)
  getRemoteScreenTrack?: (userId: string) => RemoteTrack | undefined;
}

/**
 * 개별 화면공유 비디오 컴포넌트
 */
function ScreenVideo({
  stream,
  label,
  isLocal,
  track,
}: {
  stream: MediaStream;
  label: string;
  isLocal?: boolean;
  track?: RemoteTrack;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;

    if (track && !isLocal) {
      track.attach(el);
      return () => {
        track.detach(el);
      };
    } else if (stream) {
      el.srcObject = stream;
    }
  }, [stream, track, isLocal]);

  // fullscreenchange 이벤트로 상태 동기화 (ESC 키 등)
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      container.requestFullscreen();
    }
  }, []);

  return (
    <div
      ref={containerRef}
      className={`relative rounded-lg overflow-hidden group cursor-pointer ${
        isFullscreen ? 'bg-black' : 'bg-gray-900'
      }`}
      onDoubleClick={toggleFullscreen}
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-contain"
      />
      {/* 전체화면 버튼 */}
      <button
        onClick={toggleFullscreen}
        className="absolute top-2 right-2 p-1.5 bg-black/60 rounded text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/80"
        title={isFullscreen ? '전체화면 해제' : '전체화면'}
      >
        {isFullscreen ? (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
          </svg>
        )}
      </button>
      {/* 라벨 */}
      <div className="absolute bottom-2 left-2 px-2 py-1 bg-black/60 rounded text-white text-sm">
        {label}
        {isLocal && <span className="text-gray-400 ml-1">(나)</span>}
      </div>
    </div>
  );
}

export function ScreenShareView({
  localScreenStream,
  remoteScreenStreams,
  getUserName,
  currentUserId,
  getRemoteScreenTrack,
}: ScreenShareViewProps) {
  // 모든 화면공유 스트림 수집
  const allStreams: { userId: string; stream: MediaStream; isLocal: boolean }[] = [];

  // 로컬 화면공유
  if (localScreenStream) {
    allStreams.push({
      userId: currentUserId,
      stream: localScreenStream,
      isLocal: true,
    });
  }

  // 원격 화면공유
  remoteScreenStreams.forEach((stream, userId) => {
    allStreams.push({
      userId,
      stream,
      isLocal: false,
    });
  });

  // 화면공유가 없으면 표시하지 않음
  if (allStreams.length === 0) {
    return null;
  }

  // 그리드 레이아웃 계산
  const getGridCols = (count: number) => {
    if (count === 1) return 'grid-cols-1';
    if (count === 2) return 'grid-cols-2';
    if (count <= 4) return 'grid-cols-2';
    return 'grid-cols-3';
  };

  return (
    <div className="w-full h-full p-4">
      <div className={`grid ${getGridCols(allStreams.length)} gap-4 h-full`}>
        {allStreams.map(({ userId, stream, isLocal }) => (
          <ScreenVideo
            key={userId}
            stream={stream}
            label={getUserName(userId)}
            isLocal={isLocal}
            track={!isLocal ? getRemoteScreenTrack?.(userId) : undefined}
          />
        ))}
      </div>
    </div>
  );
}
