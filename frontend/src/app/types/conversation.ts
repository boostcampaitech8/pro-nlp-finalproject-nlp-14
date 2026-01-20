// 대화 모드 관련 타입 정의

import type { ActiveCommand, SessionContext } from './command';
import type { PreviewType, PreviewData } from '@/app/stores/previewStore';

// 메시지 타입
export type MessageType = 'user' | 'agent' | 'system';

// 에이전트 응답 타입
export type AgentResponseType = 'text' | 'form' | 'result' | 'loading';

// 에이전트 메시지 데이터
export interface AgentMessageData {
  responseType: AgentResponseType;
  form?: ActiveCommand;
  previewType?: PreviewType;
  previewData?: PreviewData;
}

// 사용자 메시지 데이터
export interface UserMessageData {
  formSummary?: Record<string, string>;
}

// 메시지 인터페이스
export interface Message {
  id: string;
  type: MessageType;
  content: string;
  timestamp: Date;
  agentData?: AgentMessageData;
  userData?: UserMessageData;
}

// 레이아웃 모드
export type LayoutMode = 'center-only' | 'fullscreen' | 'center-right-merged';

// 레이아웃 설정
export interface LayoutConfig {
  showLeftSidebar: boolean;
  showRightSidebar: boolean;
  centerClass: string;
  conversationMaxWidth: string;
}

// 대화 세션 상태
export interface ConversationSession {
  id: string;
  startedAt: Date;
  context?: SessionContext;
}
