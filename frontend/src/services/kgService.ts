/**
 * KG (Knowledge Graph) CRUD API Service
 *
 * Comments, Suggestions, ActionItems, Minutes, Agenda 관련 API 호출
 */

import type {
  ActionItem,
  Agenda,
  Comment,
  DecisionReviewResponse,
  MinutesResponse,
  PRStatus,
  Suggestion,
  UpdateActionItemRequest,
  UpdateAgendaRequest,
} from '@/types';
import type { DecisionStatus } from '@/types/kg';
import api from './api';

// === Backend Response Types (camelCase from serialization_alias) ===

interface CommentRaw {
  id: string;
  content: string;
  author: { id: string; name: string };
  replies: CommentRaw[];
  pendingAgentReply: boolean;
  isErrorResponse: boolean;
  createdAt: string;
}

interface SuggestionRaw {
  id: string;
  content: string;
  author: { id: string; name: string };
  createdDecision: { id: string; content: string; status: string } | null;
  createdAt: string;
}

interface ActionItemRaw {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
  assigneeId: string | null;
  dueDate: string | null;
}

interface AgendaRaw {
  id: string;
  topic: string;
  description: string | null;
  order: number;
}

interface SupersedesRaw {
  id: string;
  content: string;
  meeting_id: string | null;
}

interface DecisionHistoryItemRaw {
  id: string;
  content: string;
  status: string;
  createdAt: string;
}

interface DecisionRaw {
  id: string;
  content: string;
  context: string | null;
  status: string;
  meeting_id: string | null;
  agendaTopic: string | null;
  meetingTitle: string | null;
  approvers: string[];
  rejectors: string[];
  createdAt: string;
  updated_at: string | null;
  suggestions: SuggestionRaw[];
  comments: CommentRaw[];
  supersedes: SupersedesRaw | null;
  history: DecisionHistoryItemRaw[];
}

interface AgendaWithDecisionsRaw {
  id: string;
  topic: string;
  description: string | null;
  order: number;
  decisions: DecisionRaw[];
}

interface MinutesResponseRaw {
  meetingId: string;
  summary: string;
  agendas: AgendaWithDecisionsRaw[];
  actionItems: ActionItemRaw[];
}

// === Transform Functions ===

function transformComment(raw: CommentRaw): Comment {
  return {
    id: raw.id,
    content: raw.content,
    author: raw.author,
    replies: raw.replies.map(transformComment),
    pendingAgentReply: raw.pendingAgentReply,
    isErrorResponse: raw.isErrorResponse,
    createdAt: raw.createdAt,
  };
}

function transformSuggestion(raw: SuggestionRaw): Suggestion {
  return {
    id: raw.id,
    content: raw.content,
    author: raw.author,
    createdDecision: raw.createdDecision ? {
      id: raw.createdDecision.id,
      content: raw.createdDecision.content,
      status: raw.createdDecision.status as DecisionStatus,
    } : null,
    createdAt: raw.createdAt,
  };
}

function transformActionItem(raw: ActionItemRaw): ActionItem {
  return {
    id: raw.id,
    content: raw.content,
    status: raw.status,
    assigneeId: raw.assigneeId,
    dueDate: raw.dueDate,
  };
}

function transformMinutes(raw: MinutesResponseRaw): MinutesResponse {
  return {
    meetingId: raw.meetingId,
    summary: raw.summary,
    agendas: raw.agendas.map((agenda) => ({
      id: agenda.id,
      topic: agenda.topic,
      description: agenda.description,
      order: agenda.order,
      decisions: agenda.decisions.map((decision) => ({
        id: decision.id,
        content: decision.content,
        context: decision.context,
        status: decision.status as DecisionStatus,
        meetingId: decision.meeting_id,
        agendaTopic: decision.agendaTopic,
        meetingTitle: decision.meetingTitle,
        approvers: decision.approvers,
        rejectors: decision.rejectors,
        createdAt: decision.createdAt,
        updatedAt: decision.updated_at,
        supersedes: decision.supersedes ? {
          id: decision.supersedes.id,
          content: decision.supersedes.content,
          meetingId: decision.supersedes.meeting_id,
        } : null,
        suggestions: decision.suggestions.map(transformSuggestion),
        comments: decision.comments.map(transformComment),
        history: (decision.history || []).map((h) => ({
          id: h.id,
          content: h.content,
          status: h.status as DecisionStatus,
          createdAt: h.createdAt,
        })),
      })),
    })),
    actionItems: raw.actionItems.map(transformActionItem),
  };
}

// === API Service ===

export const kgService = {
  // === Comments ===

  /**
   * Decision에 댓글 생성
   */
  async createComment(decisionId: string, content: string): Promise<Comment> {
    const response = await api.post<CommentRaw>(`/decisions/${decisionId}/comments`, {
      content,
    });
    return transformComment(response.data);
  },

  /**
   * 댓글에 대댓글 생성
   */
  async createReply(commentId: string, content: string): Promise<Comment> {
    const response = await api.post<CommentRaw>(`/comments/${commentId}/replies`, {
      content,
    });
    return transformComment(response.data);
  },

  /**
   * 댓글 삭제 (작성자만 가능)
   */
  async deleteComment(commentId: string): Promise<void> {
    await api.delete(`/comments/${commentId}`);
  },

  // === Suggestions ===

  /**
   * Decision에 제안 생성 (새 draft Decision 함께 생성됨)
   */
  async createSuggestion(decisionId: string, content: string, meetingId: string): Promise<Suggestion> {
    const response = await api.post<SuggestionRaw>(`/decisions/${decisionId}/suggestions`, {
      content,
      meetingId,
    });
    return transformSuggestion(response.data);
  },

  // === ActionItems ===

  /**
   * ActionItem 목록 조회 (필터 지원)
   */
  async getActionItems(filters?: {
    assigneeId?: string;
    status?: string;
  }): Promise<ActionItem[]> {
    const params = new URLSearchParams();
    if (filters?.assigneeId) params.append('assigneeId', filters.assigneeId);
    if (filters?.status) params.append('status', filters.status);
    const query = params.toString();
    const response = await api.get<ActionItemRaw[]>(`/action-items${query ? `?${query}` : ''}`);
    return response.data.map(transformActionItem);
  },

  /**
   * ActionItem 수정
   */
  async updateActionItem(
    actionItemId: string,
    data: UpdateActionItemRequest
  ): Promise<ActionItem> {
    const response = await api.put<ActionItemRaw>(`/action-items/${actionItemId}`, data);
    return transformActionItem(response.data);
  },

  /**
   * ActionItem 삭제
   */
  async deleteActionItem(actionItemId: string): Promise<void> {
    await api.delete(`/action-items/${actionItemId}`);
  },

  // === Minutes ===

  /**
   * 회의록 전체 조회 (중첩 구조: Agenda → Decision → Suggestion/Comment)
   */
  async getMinutes(meetingId: string): Promise<MinutesResponse> {
    const response = await api.get<MinutesResponseRaw>(`/meetings/${meetingId}/minutes`);
    return transformMinutes(response.data);
  },

  // === Agenda ===

  /**
   * Agenda 수정
   */
  async updateAgenda(agendaId: string, data: UpdateAgendaRequest): Promise<Agenda> {
    const response = await api.put<AgendaRaw>(`/agendas/${agendaId}`, data);
    return {
      id: response.data.id,
      topic: response.data.topic,
      description: response.data.description,
      order: response.data.order,
    };
  },

  /**
   * Agenda 삭제 (하위 Decision/Comment/Suggestion 모두 삭제)
   */
  async deleteAgenda(agendaId: string): Promise<void> {
    await api.delete(`/agendas/${agendaId}`);
  },

  // === Decision ===

  /**
   * Decision 수정
   */
  async updateDecision(
    decisionId: string,
    data: { content?: string; context?: string }
  ): Promise<void> {
    await api.put(`/decisions/${decisionId}`, data);
  },

  // === Decision Review (PR Review 통합) ===

  /**
   * 결정 리뷰 (승인/거절)
   */
  async reviewDecision(
    decisionId: string,
    action: 'approve' | 'reject'
  ): Promise<DecisionReviewResponse> {
    const response = await api.post<DecisionReviewResponse>(
      `/decisions/${decisionId}/reviews`,
      { action }
    );
    return response.data;
  },

  /**
   * 결정 승인
   */
  async approveDecision(decisionId: string): Promise<DecisionReviewResponse> {
    return this.reviewDecision(decisionId, 'approve');
  },

  /**
   * 결정 거절
   */
  async rejectDecision(decisionId: string): Promise<DecisionReviewResponse> {
    return this.reviewDecision(decisionId, 'reject');
  },

  /**
   * PR 생성 시작 (비동기 작업)
   */
  async generatePR(meetingId: string): Promise<void> {
    await api.post(`/meetings/${meetingId}/generate-pr`);
  },

  /**
   * 결정사항 존재 여부 확인
   */
  async hasDecisions(meetingId: string): Promise<boolean> {
    try {
      const minutes = await this.getMinutes(meetingId);
      return minutes.agendas.some((agenda) => agenda.decisions.length > 0);
    } catch {
      return false;
    }
  },

  /**
   * PR 상태 계산 (Minutes 데이터 기반)
   */
  calculatePRStatus(minutes: MinutesResponse): PRStatus {
    const decisions = minutes.agendas.flatMap((agenda) => agenda.decisions);
    const total = decisions.length;
    let approved = 0;
    let pending = 0;
    let rejected = 0;

    for (const d of decisions) {
      if (d.status === 'latest') {
        approved++;
      } else if (d.status === 'rejected') {
        rejected++;
      } else {
        pending++;
      }
    }

    const status = pending === 0 && total > 0 ? 'closed' : 'open';

    return {
      meetingId: minutes.meetingId,
      status,
      totalDecisions: total,
      approvedDecisions: approved,
      pendingDecisions: pending,
      rejectedDecisions: rejected,
    };
  },

  /**
   * 모든 Decision이 latest 상태인지 확인
   */
  isAllDecisionsLatest(minutes: MinutesResponse): boolean {
    const decisions = minutes.agendas.flatMap((agenda) => agenda.decisions);
    if (decisions.length === 0) return false;
    return decisions.every((d) => d.status === 'latest');
  },
};
