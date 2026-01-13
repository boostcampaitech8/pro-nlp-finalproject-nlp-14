/**
 * 클라이언트 사이드 VAD(Voice Activity Detection) 훅
 * @ricky0123/vad-web 기반 Silero VAD 사용
 */

import { useCallback, useRef, useState, useEffect } from 'react';
import { MicVAD, RealTimeVADOptions } from '@ricky0123/vad-web';
import logger from '@/utils/logger';

// VAD 세그먼트 타입
export interface VADSegment {
  startMs: number;  // 시작 시간 (밀리초)
  endMs: number;    // 종료 시간 (밀리초)
}

// VAD 메타데이터 타입
export interface VADMetadata {
  segments: VADSegment[];
  totalDurationMs: number;
  settings: {
    positiveSpeechThreshold: number;
    negativeSpeechThreshold: number;
    minSpeechFrames: number;
    preSpeechPadFrames: number;
    redemptionFrames: number;
  };
}

interface UseVADOptions {
  // VAD 감도 설정
  positiveSpeechThreshold?: number;  // 발화 시작 임계값 (기본: 0.5)
  negativeSpeechThreshold?: number;  // 발화 종료 임계값 (기본: 0.35)
  minSpeechFrames?: number;          // 최소 발화 프레임 수 (기본: 3)
  preSpeechPadFrames?: number;       // 발화 전 패딩 프레임 (기본: 1)
  redemptionFrames?: number;         // 발화 종료 유예 프레임 (기본: 8)
}

interface UseVADReturn {
  // 상태
  isVADReady: boolean;
  isVADActive: boolean;
  isSpeaking: boolean;
  vadError: string | null;

  // VAD 메타데이터
  vadMetadata: VADMetadata | null;
  currentSegments: VADSegment[];

  // 액션
  startVAD: (stream: MediaStream) => Promise<void>;
  stopVAD: () => void;
  resetVAD: () => void;
}

// 기본 설정
const DEFAULT_OPTIONS: Required<UseVADOptions> = {
  positiveSpeechThreshold: 0.5,
  negativeSpeechThreshold: 0.35,
  minSpeechFrames: 3,
  preSpeechPadFrames: 1,
  redemptionFrames: 8,
};

export function useVAD(options: UseVADOptions = {}): UseVADReturn {
  const settings = { ...DEFAULT_OPTIONS, ...options };

  const [isVADReady, setIsVADReady] = useState(false);
  const [isVADActive, setIsVADActive] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [vadError, setVadError] = useState<string | null>(null);
  const [currentSegments, setCurrentSegments] = useState<VADSegment[]>([]);

  const vadRef = useRef<MicVAD | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const speechStartRef = useRef<number | null>(null);
  const segmentsRef = useRef<VADSegment[]>([]);

  /**
   * VAD 시작
   */
  const startVAD = useCallback(async (stream: MediaStream) => {
    if (vadRef.current) {
      logger.log('[useVAD] VAD already active');
      return;
    }

    try {
      setVadError(null);
      logger.log('[useVAD] Starting VAD...');

      // 시작 시간 기록
      startTimeRef.current = Date.now();
      segmentsRef.current = [];
      setCurrentSegments([]);

      const vadOptions: Partial<RealTimeVADOptions> = {
        positiveSpeechThreshold: settings.positiveSpeechThreshold,
        negativeSpeechThreshold: settings.negativeSpeechThreshold,
        minSpeechFrames: settings.minSpeechFrames,
        preSpeechPadFrames: settings.preSpeechPadFrames,
        redemptionFrames: settings.redemptionFrames,

        // 콜백
        onSpeechStart: () => {
          const now = Date.now();
          speechStartRef.current = now;
          setIsSpeaking(true);
          logger.log('[useVAD] Speech started at', now - (startTimeRef.current || 0), 'ms');
        },

        onSpeechEnd: (audio: Float32Array) => {
          const now = Date.now();
          if (speechStartRef.current && startTimeRef.current) {
            const segment: VADSegment = {
              startMs: speechStartRef.current - startTimeRef.current,
              endMs: now - startTimeRef.current,
            };
            segmentsRef.current.push(segment);
            setCurrentSegments([...segmentsRef.current]);
            logger.log('[useVAD] Speech ended:', segment, 'duration:', segment.endMs - segment.startMs, 'ms');
          }
          speechStartRef.current = null;
          setIsSpeaking(false);
        },

        onVADMisfire: () => {
          // 짧은 발화로 감지되지 않음
          speechStartRef.current = null;
          setIsSpeaking(false);
        },
      };

      // stream에서 VAD 생성
      const vad = await MicVAD.new({
        ...vadOptions,
        stream,
      });

      vadRef.current = vad;
      setIsVADReady(true);
      setIsVADActive(true);

      // VAD 시작
      vad.start();
      logger.log('[useVAD] VAD started successfully');

    } catch (err) {
      logger.error('[useVAD] Failed to start VAD:', err);
      setVadError('VAD 초기화에 실패했습니다.');
      setIsVADReady(false);
      setIsVADActive(false);
    }
  }, [settings]);

  /**
   * VAD 중지
   */
  const stopVAD = useCallback(() => {
    if (!vadRef.current) {
      return;
    }

    try {
      // 현재 발화 중이면 종료 처리
      if (speechStartRef.current && startTimeRef.current) {
        const now = Date.now();
        const segment: VADSegment = {
          startMs: speechStartRef.current - startTimeRef.current,
          endMs: now - startTimeRef.current,
        };
        segmentsRef.current.push(segment);
        setCurrentSegments([...segmentsRef.current]);
        logger.log('[useVAD] Final speech segment:', segment);
      }

      vadRef.current.pause();
      vadRef.current.destroy();
      vadRef.current = null;

      setIsVADActive(false);
      setIsSpeaking(false);
      speechStartRef.current = null;

      logger.log('[useVAD] VAD stopped, segments:', segmentsRef.current.length);
    } catch (err) {
      logger.error('[useVAD] Failed to stop VAD:', err);
    }
  }, []);

  /**
   * VAD 메타데이터 생성
   */
  const getVADMetadata = useCallback((): VADMetadata | null => {
    if (!startTimeRef.current) {
      return null;
    }

    const totalDurationMs = Date.now() - startTimeRef.current;

    return {
      segments: [...segmentsRef.current],
      totalDurationMs,
      settings: {
        positiveSpeechThreshold: settings.positiveSpeechThreshold,
        negativeSpeechThreshold: settings.negativeSpeechThreshold,
        minSpeechFrames: settings.minSpeechFrames,
        preSpeechPadFrames: settings.preSpeechPadFrames,
        redemptionFrames: settings.redemptionFrames,
      },
    };
  }, [settings]);

  /**
   * VAD 상태 초기화
   */
  const resetVAD = useCallback(() => {
    stopVAD();
    startTimeRef.current = null;
    segmentsRef.current = [];
    setCurrentSegments([]);
    setVadError(null);
    setIsVADReady(false);
  }, [stopVAD]);

  /**
   * cleanup
   */
  useEffect(() => {
    return () => {
      if (vadRef.current) {
        try {
          vadRef.current.pause();
          vadRef.current.destroy();
        } catch {
          // ignore cleanup errors
        }
      }
    };
  }, []);

  return {
    isVADReady,
    isVADActive,
    isSpeaking,
    vadError,
    vadMetadata: isVADActive || segmentsRef.current.length > 0 ? getVADMetadata() : null,
    currentSegments,
    startVAD,
    stopVAD,
    resetVAD,
  };
}
