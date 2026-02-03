/**
 * useMeetingTopics - SSE 기반 실시간 토픽 스트리밍 훅
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { TopicFeedResponse, TopicItem } from '@/types';
import { meetingTopicService } from '@/services/meetingTopicService';
import logger from '@/utils/logger';

interface UseMeetingTopicsOptions {
  /** SSE 활성화 여부 */
  enabled?: boolean;
  /** SSE 연결 실패 시 폴링 폴백 간격 (ms, 기본값: 5000) */
  fallbackInterval?: number;
}

interface UseMeetingTopicsReturn {
  topics: TopicItem[];
  isL1Running: boolean;
  pendingChunks: number;
}

export function useMeetingTopics(
  meetingId: string | null,
  options: UseMeetingTopicsOptions = {}
): UseMeetingTopicsReturn {
  const { enabled = true, fallbackInterval = 5000 } = options;

  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [isL1Running, setIsL1Running] = useState(false);
  const [pendingChunks, setPendingChunks] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const fallbackIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 응답 데이터 업데이트 헬퍼
  const updateFromResponse = useCallback((data: TopicFeedResponse) => {
    if (!mountedRef.current) return;
    setTopics(data.topics);
    setIsL1Running(data.isL1Running);
    setPendingChunks(data.pendingChunks);
  }, []);

  // 단발성 조회 (폴백용)
  const fetchTopics = useCallback(async () => {
    if (!meetingId || !mountedRef.current) return;

    try {
      const response = await meetingTopicService.getMeetingTopics(meetingId);
      updateFromResponse(response);
    } catch (err) {
      if (!mountedRef.current) return;
      logger.error('[useMeetingTopics] 조회 오류:', err);
    }
  }, [meetingId, updateFromResponse]);

  // SSE 연결 정리
  const cleanupSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // 폴백 폴링 정리
  const cleanupFallback = useCallback(() => {
    if (fallbackIntervalRef.current) {
      clearInterval(fallbackIntervalRef.current);
      fallbackIntervalRef.current = null;
    }
  }, []);

  // 폴백 폴링 시작
  const startFallbackPolling = useCallback(() => {
    cleanupFallback();
    logger.info('[useMeetingTopics] SSE 실패, 폴백 폴링 시작');

    // 즉시 한 번 조회
    fetchTopics();

    // 주기적 폴링
    fallbackIntervalRef.current = setInterval(fetchTopics, fallbackInterval);
  }, [cleanupFallback, fetchTopics, fallbackInterval]);

  // SSE 연결
  const connectSSE = useCallback(() => {
    if (!meetingId || !enabled) return;

    const token = localStorage.getItem('accessToken');
    if (!token) {
      logger.warn('[useMeetingTopics] 토큰 없음, 폴백 폴링 사용');
      startFallbackPolling();
      return;
    }

    cleanupSSE();
    cleanupFallback();

    const url = meetingTopicService.getStreamUrl(meetingId, token);
    logger.info('[useMeetingTopics] SSE 연결 시도:', url.replace(token, '***'));

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    // 초기 데이터 수신
    eventSource.addEventListener('init', (event) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(event.data) as TopicFeedResponse;
        updateFromResponse(data);
        logger.info('[useMeetingTopics] SSE 초기 데이터 수신');
      } catch (err) {
        logger.error('[useMeetingTopics] init 파싱 오류:', err);
      }
    });

    // 업데이트 수신
    eventSource.addEventListener('update', (event) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(event.data) as TopicFeedResponse;
        updateFromResponse(data);
        logger.debug('[useMeetingTopics] 토픽 업데이트 수신');
      } catch (err) {
        logger.error('[useMeetingTopics] update 파싱 오류:', err);
      }
    });

    // 에러 처리
    eventSource.addEventListener('error', (event) => {
      if (!mountedRef.current) return;

      logger.error('[useMeetingTopics] SSE 에러:', event);
      cleanupSSE();

      // 재연결 시도 (3초 후)
      reconnectTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current && enabled) {
          logger.info('[useMeetingTopics] SSE 재연결 시도...');
          connectSSE();
        }
      }, 3000);
    });

    // 연결 열림
    eventSource.onopen = () => {
      logger.info('[useMeetingTopics] SSE 연결 열림');
    };
  }, [meetingId, enabled, cleanupSSE, cleanupFallback, startFallbackPolling, updateFromResponse]);

  // SSE 연결 관리
  useEffect(() => {
    if (!enabled || !meetingId) {
      cleanupSSE();
      cleanupFallback();
      return;
    }

    connectSSE();

    return () => {
      cleanupSSE();
      cleanupFallback();
    };
  }, [meetingId, enabled, connectSSE, cleanupSSE, cleanupFallback]);

  // 언마운트 시 정리
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  return {
    topics,
    isL1Running,
    pendingChunks,
  };
}
