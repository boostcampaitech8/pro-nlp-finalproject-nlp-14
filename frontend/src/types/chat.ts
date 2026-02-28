/**
 * 채팅 관련 타입 정의
 */

export interface ChatMessage {
  id: string;
  userId: string;
  userName: string;
  content: string;
  createdAt: string;
}

export type AgentState = 'idle' | 'listening' | 'thinking' | 'speaking';
