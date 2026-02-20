/**
 * 테스트 유틸리티
 * 공통 렌더링 함수 및 모의 객체 생성 헬퍼
 */

import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';

// 기본 Provider 래퍼
interface AllProvidersProps {
  children: ReactNode;
}

function AllProviders({ children }: AllProvidersProps) {
  return <BrowserRouter>{children}</BrowserRouter>;
}

// 커스텀 render 함수
function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

// 모든 testing-library 함수 재export
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';

// 커스텀 render를 기본 render로 교체
export { customRender as render };

/**
 * MediaStream 모의 객체 생성
 */
export function createMockMediaStream(
  options: {
    hasAudio?: boolean;
    hasVideo?: boolean;
  } = {}
): MediaStream {
  const { hasAudio = true, hasVideo = false } = options;

  const audioTrack = hasAudio
    ? {
        kind: 'audio' as const,
        id: `audio-track-${Math.random()}`,
        enabled: true,
        muted: false,
        readyState: 'live' as MediaStreamTrackState,
        stop: () => {},
        clone: () => audioTrack,
        getSettings: () => ({}),
        getConstraints: () => ({}),
        getCapabilities: () => ({}),
        applyConstraints: async () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => true,
        onended: null,
        onmute: null,
        onunmute: null,
        label: 'Mock Audio Track',
        contentHint: '',
      }
    : null;

  const videoTrack = hasVideo
    ? {
        kind: 'video' as const,
        id: `video-track-${Math.random()}`,
        enabled: true,
        muted: false,
        readyState: 'live' as MediaStreamTrackState,
        stop: () => {},
        clone: () => videoTrack,
        getSettings: () => ({}),
        getConstraints: () => ({}),
        getCapabilities: () => ({}),
        applyConstraints: async () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => true,
        onended: null,
        onmute: null,
        onunmute: null,
        label: 'Mock Video Track',
        contentHint: '',
      }
    : null;

  const tracks = [audioTrack, videoTrack].filter(Boolean) as MediaStreamTrack[];

  return {
    id: `stream-${Math.random()}`,
    active: true,
    getTracks: () => tracks,
    getAudioTracks: () => tracks.filter((t) => t.kind === 'audio'),
    getVideoTracks: () => tracks.filter((t) => t.kind === 'video'),
    addTrack: () => {},
    removeTrack: () => {},
    clone: () => createMockMediaStream(options),
    getTrackById: () => null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
    onaddtrack: null,
    onremovetrack: null,
  } as unknown as MediaStream;
}

/**
 * RoomParticipant 모의 객체 생성
 */
export function createMockParticipant(
  overrides: Partial<{
    userId: string;
    userName: string;
    role: string;
    audioMuted: boolean;
    isScreenSharing: boolean;
  }> = {}
) {
  return {
    userId: overrides.userId ?? `user-${Math.random().toString(36).slice(2)}`,
    userName: overrides.userName ?? 'Test User',
    role: overrides.role ?? 'participant',
    audioMuted: overrides.audioMuted ?? false,
    isScreenSharing: overrides.isScreenSharing ?? false,
  };
}

/**
 * RTCPeerConnection 모의 객체 생성
 */
export function createMockPeerConnection(): RTCPeerConnection {
  return new RTCPeerConnection();
}

/**
 * 비동기 대기 헬퍼
 */
export function waitFor(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Zustand 스토어 리셋 헬퍼
 */
export function resetAllStores() {
  // 필요시 각 스토어의 reset 함수 호출
}
