/**
 * PR Review 관련 타입 정의
 * main 브랜치 API 스키마 기반
 */

export type DecisionStatus = 'draft' | 'approved' | 'rejected' | 'latest' | 'outdated' | 'pending' | 'merged';

// main API의 DecisionResponse에 맞춤
export interface Decision {
  id: string;
  content: string;
  context?: string | null;
  status: DecisionStatus;
  agendaTopic?: string | null;
  meetingTitle?: string | null;
  approvers: string[];
  rejectors: string[];
  createdAt: string;
}

// main API의 DecisionListResponse에 맞춤
export interface DecisionListResponse {
  meetingId: string;
  decisions: Decision[];
}

// main API의 DecisionReviewRequest에 맞춤
export interface DecisionReviewRequest {
  action: 'approve' | 'reject';
}

// main API의 DecisionReviewResponse에 맞춤
export interface DecisionReviewResponse {
  decisionId: string;
  action: string;
  success: boolean;
  merged: boolean;
  status: string;
  approversCount: number;
  participantsCount: number;
}

// 프론트엔드 UI용 타입 (아젠다별 그룹화)
export interface PRAgenda {
  id: string;
  topic: string;
  decisions: Decision[];
}

export interface PRParticipant {
  id: string;
  name: string;
}

// 프론트엔드 UI용 회의록 타입
export interface PRMinutes {
  meetingId: string;
  title: string;
  description?: string | null;
  agendas: PRAgenda[];
  participants: PRParticipant[];
}

// 프론트엔드 UI용 PR 상태 (클라이언트에서 계산)
export interface PRStatus {
  meetingId: string;
  status: 'open' | 'closed';
  totalDecisions: number;
  approvedDecisions: number;
  pendingDecisions: number;
  rejectedDecisions: number;
}
