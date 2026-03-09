/**
 * 오디오 레벨 분석 훅
 * Web Audio API를 사용하여 MediaStream의 볼륨 레벨을 실시간으로 분석
 */

import { useEffect, useRef, useState, useCallback } from 'react';

// 오디오 레벨 단계 (0: 무음, 1: 낮음, 2: 중간, 3: 높음)
export type AudioLevel = 0 | 1 | 2 | 3;

interface AudioAnalyzer {
  analyser: AnalyserNode;
  dataArray: Uint8Array<ArrayBuffer>;
  source: MediaStreamAudioSourceNode;
}

// 볼륨 임계값 설정
const THRESHOLD_LOW = 10;    // 낮은 볼륨 시작
const THRESHOLD_MID = 30;    // 중간 볼륨 시작
const THRESHOLD_HIGH = 60;   // 높은 볼륨 시작

/**
 * 단일 스트림의 오디오 레벨 분석
 */
export function useAudioLevel(stream: MediaStream | null): AudioLevel {
  const [level, setLevel] = useState<AudioLevel>(0);
  const analyzerRef = useRef<AudioAnalyzer | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!stream) {
      setLevel(0);
      return;
    }

    // AudioContext 생성
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    // AnalyserNode 설정
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    // MediaStream 연결
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    analyzerRef.current = { analyser, dataArray, source };

    // 레벨 분석 루프
    const analyze = () => {
      if (!analyzerRef.current) return;

      const { analyser, dataArray } = analyzerRef.current;
      analyser.getByteFrequencyData(dataArray);

      // 평균 볼륨 계산
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;

      // 3단계 레벨로 변환
      let newLevel: AudioLevel = 0;
      if (average >= THRESHOLD_HIGH) {
        newLevel = 3;
      } else if (average >= THRESHOLD_MID) {
        newLevel = 2;
      } else if (average >= THRESHOLD_LOW) {
        newLevel = 1;
      }

      setLevel(newLevel);
      animationFrameRef.current = requestAnimationFrame(analyze);
    };

    analyze();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (analyzerRef.current) {
        analyzerRef.current.source.disconnect();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      analyzerRef.current = null;
    };
  }, [stream]);

  return level;
}

/**
 * 여러 스트림의 오디오 레벨을 동시에 분석
 */
export function useMultiAudioLevels(
  streams: Map<string, MediaStream>,
  localStream: MediaStream | null,
  currentUserId: string
): Map<string, AudioLevel> {
  const [levels, setLevels] = useState<Map<string, AudioLevel>>(new Map());
  const analyzersRef = useRef<Map<string, AudioAnalyzer>>(new Map());
  const animationFrameRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const updateLevels = useCallback(() => {
    const newLevels = new Map<string, AudioLevel>();

    analyzersRef.current.forEach((analyzer, odId) => {
      const { analyser, dataArray } = analyzer;
      analyser.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;

      let level: AudioLevel = 0;
      if (average >= THRESHOLD_HIGH) {
        level = 3;
      } else if (average >= THRESHOLD_MID) {
        level = 2;
      } else if (average >= THRESHOLD_LOW) {
        level = 1;
      }

      newLevels.set(odId, level);
    });

    setLevels(newLevels);
    animationFrameRef.current = requestAnimationFrame(updateLevels);
  }, []);

  useEffect(() => {
    // AudioContext 생성 (한 번만)
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    const audioContext = audioContextRef.current;

    // 모든 스트림에 대해 analyzer 설정
    const allStreams = new Map<string, MediaStream>();

    // 원격 스트림 추가
    streams.forEach((stream, odId) => {
      allStreams.set(odId, stream);
    });

    // 로컬 스트림 추가
    if (localStream && currentUserId) {
      allStreams.set(currentUserId, localStream);
    }

    // 새로운 스트림에 대해 analyzer 생성
    allStreams.forEach((stream, odId) => {
      if (!analyzersRef.current.has(odId)) {
        try {
          const analyser = audioContext.createAnalyser();
          analyser.fftSize = 256;
          analyser.smoothingTimeConstant = 0.8;

          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);

          const source = audioContext.createMediaStreamSource(stream);
          source.connect(analyser);

          analyzersRef.current.set(odId, { analyser, dataArray, source });
        } catch (e) {
          console.error(`[useMultiAudioLevels] Failed to create analyzer for ${odId}:`, e);
        }
      }
    });

    // 제거된 스트림의 analyzer 정리
    analyzersRef.current.forEach((analyzer, odId) => {
      if (!allStreams.has(odId)) {
        analyzer.source.disconnect();
        analyzersRef.current.delete(odId);
      }
    });

    // 분석 루프 시작
    if (!animationFrameRef.current && analyzersRef.current.size > 0) {
      updateLevels();
    }

    return () => {
      // 컴포넌트 언마운트 시 정리
    };
  }, [streams, localStream, currentUserId, updateLevels]);

  // 클린업
  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      analyzersRef.current.forEach((analyzer) => {
        analyzer.source.disconnect();
      });
      analyzersRef.current.clear();
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
    };
  }, []);

  return levels;
}
