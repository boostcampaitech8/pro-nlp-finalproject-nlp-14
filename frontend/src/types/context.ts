/**
 * Context/Topic API 타입
 */

/** 개별 토픽 항목 */
export interface TopicItem {
  id: string;
  name: string;
  summary: string;
  startTurn: number;
  endTurn: number;
  keywords: string[];
}

/** 토픽 피드 API 응답 */
export interface TopicFeedResponse {
  meetingId: string;
  pendingChunks: number;
  isL1Running: boolean;
  currentTopic: string | null;
  topics: TopicItem[];
  updatedAt: string;
}
