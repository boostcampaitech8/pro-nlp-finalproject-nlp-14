/**
 * PR Review API Service
 *
 * main 브랜치 API 기반 회의록 리뷰 관련 API 호출
 */

import type { Decision, DecisionListResponse, DecisionReviewResponse, PRStatus } from '@/types';
import api from './api';

// Backend 응답 타입 (snake_case)
interface DecisionRaw {
  id: string;
  content: string;
  context?: string | null;
  status: string;
  agendaTopic?: string | null;
  meetingTitle?: string | null;
  approvers: string[];
  rejectors: string[];
  createdAt: string;
}

interface DecisionListResponseRaw {
  meetingId: string;
  decisions: DecisionRaw[];
}

interface DecisionReviewResponseRaw {
  decisionId: string;
  action: string;
  success: boolean;
  merged: boolean;
  status: string;
  approversCount: number;
  participantsCount: number;
}

// 변환 함수
function transformDecision(raw: DecisionRaw): Decision {
  return {
    id: raw.id,
    content: raw.content,
    context: raw.context,
    status: raw.status as Decision['status'],
    agendaTopic: raw.agendaTopic,
    meetingTitle: raw.meetingTitle,
    approvers: raw.approvers,
    rejectors: raw.rejectors,
    createdAt: raw.createdAt,
  };
}

function transformDecisionList(raw: DecisionListResponseRaw): DecisionListResponse {
  return {
    meetingId: raw.meetingId,
    decisions: raw.decisions.map(transformDecision),
  };
}

// 결정사항 목록에서 PR 상태 계산
function calculatePRStatus(meetingId: string, decisions: Decision[]): PRStatus {
  const total = decisions.length;
  let approved = 0;
  let pending = 0;
  let rejected = 0;

  for (const d of decisions) {
    if (d.status === 'approved' || d.status === 'merged' || d.status === 'latest') {
      approved++;
    } else if (d.status === 'rejected') {
      rejected++;
    } else {
      pending++;
    }
  }

  const status = pending === 0 && total > 0 ? 'closed' : 'open';

  return {
    meetingId,
    status,
    totalDecisions: total,
    approvedDecisions: approved,
    pendingDecisions: pending,
    rejectedDecisions: rejected,
  };
}

export const prReviewService = {
  /**
   * 회의의 결정 목록 조회
   */
  async getMeetingDecisions(meetingId: string): Promise<DecisionListResponse> {
    const response = await api.get<DecisionListResponseRaw>(`/meetings/${meetingId}/decisions`);
    return transformDecisionList(response.data);
  },

  /**
   * 결정 상세 조회
   */
  async getDecision(decisionId: string): Promise<Decision> {
    const response = await api.get<DecisionRaw>(`/decisions/${decisionId}`);
    return transformDecision(response.data);
  },

  /**
   * PR 상태 조회 (클라이언트에서 계산)
   */
  async getPRStatus(meetingId: string): Promise<PRStatus> {
    const { decisions } = await this.getMeetingDecisions(meetingId);
    return calculatePRStatus(meetingId, decisions);
  },

  /**
   * 결정 리뷰 (승인/거절)
   */
  async reviewDecision(
    decisionId: string,
    action: 'approve' | 'reject'
  ): Promise<DecisionReviewResponse> {
    const response = await api.post<DecisionReviewResponseRaw>(`/decisions/${decisionId}/reviews`, {
      action,
    });
    return response.data;
  },

  /**
   * 결정 승인 (편의 메서드)
   */
  async approveDecision(decisionId: string): Promise<DecisionReviewResponse> {
    return this.reviewDecision(decisionId, 'approve');
  },

  /**
   * 결정 거절 (편의 메서드)
   */
  async rejectDecision(decisionId: string): Promise<DecisionReviewResponse> {
    return this.reviewDecision(decisionId, 'reject');
  },

  /**
   * PR 생성 시작 (비동기 작업)
   * 트랜스크립트 기반으로 Agenda와 Decision 추출
   */
  async generatePR(meetingId: string): Promise<void> {
    await api.post(`/meetings/${meetingId}/generate-pr`);
  },

  /**
   * 결정사항 존재 여부 확인
   */
  async hasDecisions(meetingId: string): Promise<boolean> {
    try {
      const { decisions } = await this.getMeetingDecisions(meetingId);
      return decisions.length > 0;
    } catch {
      return false;
    }
  },
};
