/**
 * KG (Knowledge Graph) CRUD Types
 *
 * Comments, Suggestions, ActionItems, Minutes 관련 타입 정의
 */

// === Common Types ===

export interface UserBrief {
  id: string;
  name: string;
}

/**
 * Decision 상태 정의
 * - draft: 리뷰 대기 중 (AI 생성 또는 Suggestion에서 생성)
 * - latest: 전원 승인 완료 (GT, Ground Truth)
 * - outdated: latest였다가 다른 회의에서 새 latest로 대체됨
 * - superseded: draft였다가 Suggestion 수락으로 새 draft로 대체됨
 * - rejected: 거절됨
 */
export type DecisionStatus = 'draft' | 'latest' | 'outdated' | 'superseded' | 'rejected';

export interface DecisionBrief {
  id: string;
  content: string;
  status: DecisionStatus;
}

/**
 * 이전 버전 Decision 정보 (GT 표시용)
 */
export interface SupersedesInfo {
  id: string;
  content: string;
  meetingId: string | null;
}

/**
 * Decision 히스토리 아이템 (superseded 체인)
 * 같은 Meeting 스코프 내에서 Suggestion으로 superseded된 이전 버전들
 */
export interface DecisionHistoryItem {
  id: string;
  content: string;
  status: DecisionStatus;
  createdAt: string;
}

export interface SpanRef {
  transcript_id: string;
  start_utt_id: string;
  end_utt_id: string;
  sub_start: number | null;
  sub_end: number | null;
  start_ms: number | null;
  end_ms: number | null;
  topic_id: string | null;
  topic_name: string | null;
}

// === Comment Types ===

export interface Comment {
  id: string;
  content: string;
  author: UserBrief;
  replies: Comment[];
  pendingAgentReply: boolean;
  isErrorResponse: boolean;
  createdAt: string;
}

export interface CreateCommentRequest {
  content: string;
}

// === Suggestion Types ===

export interface Suggestion {
  id: string;
  content: string;
  author: UserBrief;
  createdDecision: DecisionBrief | null;
  createdAt: string;
}

export interface CreateSuggestionRequest {
  content: string;
  meetingId: string; // Suggestion이 생성되는 Meeting ID (스코프)
}

// === ActionItem Types ===

export type ActionItemStatus = 'pending' | 'in_progress' | 'completed';

export interface ActionItem {
  id: string;
  content: string;
  status: ActionItemStatus;
  assigneeId: string | null;
  dueDate: string | null;
}

export interface UpdateActionItemRequest {
  content?: string;
  assigneeId?: string | null;
  dueDate?: string | null;
  status?: ActionItemStatus;
}

// === Agenda Types ===

export interface Agenda {
  id: string;
  topic: string;
  description: string | null;
  order: number;
}

export interface UpdateAgendaRequest {
  topic?: string;
  description?: string | null;
}

// === Decision with Review Types (for Minutes) ===

export interface DecisionWithReview {
  id: string;
  content: string;
  context: string | null;
  evidence: SpanRef[];
  status: DecisionStatus;
  meetingId: string | null;
  agendaTopic: string | null;
  meetingTitle: string | null;
  approvers: string[];
  rejectors: string[];
  createdAt: string;
  updatedAt: string | null;
  suggestions: Suggestion[];
  comments: Comment[];
  /** 이전 버전 정보 (GT 표시용) */
  supersedes: SupersedesInfo | null;
  /** 히스토리: 같은 Meeting 스코프 내 superseded된 모든 이전 버전 */
  history: DecisionHistoryItem[];
}

// === Agenda with Decisions (for Minutes) ===

export interface AgendaWithDecisions {
  id: string;
  topic: string;
  description: string | null;
  order: number;
  evidence: SpanRef[];
  decisions: DecisionWithReview[];
}

// === Minutes Response ===

export interface MinutesResponse {
  meetingId: string;
  meetingTitle: string | null;
  summary: string;
  agendas: AgendaWithDecisions[];
  actionItems: ActionItem[];
}
