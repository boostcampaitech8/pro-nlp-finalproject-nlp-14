/**
 * 화면공유 표시 컴포넌트
 * 여러 명의 화면공유를 그리드 레이아웃으로 표시
 */

import { useEffect, useRef } from 'react';
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

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;

    if (track && !isLocal) {
      // 원격: LiveKit SDK의 attach() 사용 (adaptiveStream 호환)
      track.attach(el);
      return () => {
        track.detach(el);
      };
    } else if (stream) {
      // 로컬: 기존 srcObject 방식
      el.srcObject = stream;
    }
  }, [stream, track, isLocal]);

  return (
    <div className="relative bg-gray-900 rounded-lg overflow-hidden">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-contain"
      />
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
