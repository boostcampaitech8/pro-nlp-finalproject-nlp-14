/**
 * 회의 토픽 서비스
 */

import type { TopicFeedResponse } from '@/types';
import api from './api';

// 환경변수에서 API URL 가져오기 (기본값: 상대 경로)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const meetingTopicService = {
  /**
   * 회의의 실시간 L1 토픽 조회 (단발성)
   * @param meetingId - 회의 UUID
   * @returns 최신순 정렬된 토픽 목록
   */
  async getMeetingTopics(meetingId: string): Promise<TopicFeedResponse> {
    const response = await api.get<TopicFeedResponse>(
      `/meetings/${meetingId}/context/topics`
    );
    return response.data;
  },

  /**
   * SSE 스트리밍 URL 생성
   * @param meetingId - 회의 UUID
   * @param token - JWT 액세스 토큰
   * @returns SSE 스트리밍 URL
   */
  getStreamUrl(meetingId: string, token: string): string {
    return `${API_BASE_URL}/meetings/${meetingId}/context/topics/stream?token=${encodeURIComponent(token)}`;
  },
};
