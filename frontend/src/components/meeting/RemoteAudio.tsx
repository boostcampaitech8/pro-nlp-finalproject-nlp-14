/**
 * 원격 오디오 재생 컴포넌트
 * - HTMLAudioElement를 사용하여 안정적인 오디오 재생
 * - GainNode를 통한 볼륨 조절 지원 (0-2 범위)
 * - setSinkId를 통한 출력 장치 선택 지원
 */

import { useEffect, useRef } from 'react';
import logger from '@/utils/logger';

interface RemoteAudioProps {
  stream: MediaStream;
  odId: string;
  outputDeviceId: string | null;
  volume: number;
}

export function RemoteAudio({
  stream,
  odId,
  outputDeviceId,
  volume,
}: RemoteAudioProps) {
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
    logger.log('[RemoteAudio] Setting up audio for:', odId, 'tracks:', stream.getAudioTracks().length);

    // 스트림의 오디오 트랙 확인
    const audioTracks = stream.getAudioTracks();
    if (audioTracks.length === 0) {
      logger.warn('[RemoteAudio] No audio tracks in stream for:', odId);
      return;
    }

    audioTracks.forEach((track, i) => {
      logger.log(`[RemoteAudio] Track ${i}: enabled=${track.enabled}, muted=${track.muted}, readyState=${track.readyState}`);
    });

    // audio 요소에 스트림 연결
    audioElement.srcObject = stream;

    // Web Audio API로 볼륨 조절 (GainNode 사용)
    try {
      const audioContext = new AudioContext();

      // AudioContext가 suspended 상태면 resume
      if (audioContext.state === 'suspended') {
        logger.log('[RemoteAudio] Resuming suspended AudioContext');
        audioContext.resume().catch((err) => {
          logger.error('[RemoteAudio] Failed to resume AudioContext:', err);
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
      logger.log('[RemoteAudio] Audio setup complete for:', odId);
    } catch (err) {
      logger.error('[RemoteAudio] Failed to setup Web Audio API, using audio element:', err);
      // Web Audio API 실패시 audio 요소로 재생
      audioElement.muted = false;
      audioElement.volume = 1.0;
      isSetupRef.current = true;
    }

    // 재생 시작
    audioElement.play().catch((err) => {
      logger.error('[RemoteAudio] Failed to play audio:', err);
    });

    return () => {
      logger.log('[RemoteAudio] Cleaning up audio for:', odId);
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
      logger.log('[RemoteAudio] Volume changed for', odId, ':', volume);
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
          logger.error('[RemoteAudio] Failed to set output device:', err);
        });
      }
    }
  }, [outputDeviceId]);

  return <audio ref={audioRef} autoPlay playsInline style={{ display: 'none' }} />;
}
