/**
 * 오디오 장치 목록 관리 훅
 * 마이크 입력 및 스피커 출력 장치 목록 조회
 */

import { useState, useEffect, useCallback } from 'react';

export interface AudioDevice {
  deviceId: string;
  label: string;
  kind: 'audioinput' | 'audiooutput';
}

export function useAudioDevices() {
  const [audioInputDevices, setAudioInputDevices] = useState<AudioDevice[]>([]);
  const [audioOutputDevices, setAudioOutputDevices] = useState<AudioDevice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // setSinkId 지원 여부 확인
  const isSinkIdSupported = typeof HTMLAudioElement !== 'undefined' &&
    'setSinkId' in HTMLAudioElement.prototype;

  /**
   * 장치 목록 새로고침
   */
  const refreshDevices = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const devices = await navigator.mediaDevices.enumerateDevices();

      const inputs: AudioDevice[] = devices
        .filter((d) => d.kind === 'audioinput')
        .map((d, index) => ({
          deviceId: d.deviceId,
          // 레이블이 없으면 기본 이름 사용 (권한 미허용 시)
          label: d.label || `마이크 ${index + 1}`,
          kind: 'audioinput' as const,
        }));

      const outputs: AudioDevice[] = devices
        .filter((d) => d.kind === 'audiooutput')
        .map((d, index) => ({
          deviceId: d.deviceId,
          label: d.label || `스피커 ${index + 1}`,
          kind: 'audiooutput' as const,
        }));

      setAudioInputDevices(inputs);
      setAudioOutputDevices(outputs);
    } catch (err) {
      console.error('[useAudioDevices] Failed to enumerate devices:', err);
      setError('장치 목록을 불러올 수 없습니다.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * 컴포넌트 마운트 시 장치 목록 조회 및 변경 감지
   */
  useEffect(() => {
    refreshDevices();

    // 장치 연결/해제 감지
    navigator.mediaDevices.addEventListener('devicechange', refreshDevices);

    return () => {
      navigator.mediaDevices.removeEventListener('devicechange', refreshDevices);
    };
  }, [refreshDevices]);

  return {
    audioInputDevices,
    audioOutputDevices,
    isLoading,
    error,
    isSinkIdSupported,
    refreshDevices,
  };
}
