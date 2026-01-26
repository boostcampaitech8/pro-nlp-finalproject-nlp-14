/**
 * PR Review Store
 *
 * 회의록 리뷰 상태 관리 (main API 기반)
 */

import type {
  Decision,
  DecisionReviewResponse,
  ErrorResponse,
  MeetingWithParticipants,
  PRAgenda,
  PRStatus,
} from '@/types';
import axios from 'axios';
import { create } from 'zustand';

import { meetingService } from '@/services/meetingService';
import { prReviewService } from '@/services/prReviewService';

// API 에러에서 사용자 친화적 메시지 추출
function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error) && error.response?.data) {
    const data = error.response.data;
    if (data.detail?.message) {
      return data.detail.message;
    }
    if ((data as ErrorResponse).message) {
      return (data as ErrorResponse).message;
    }
  }
  return fallback;
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

// decisions를 agendaTopic 기준으로 그룹화
function groupDecisionsByAgenda(decisions: Decision[]): PRAgenda[] {
  const agendaMap = new Map<string, Decision[]>();

  for (const decision of decisions) {
    const topic = decision.agendaTopic || 'Other';
    if (!agendaMap.has(topic)) {
      agendaMap.set(topic, []);
    }
    agendaMap.get(topic)!.push(decision);
  }

  // 아젠다 목록 생성 (토픽 이름순 정렬)
  const agendas: PRAgenda[] = [];
  let order = 1;
  for (const [topic, topicDecisions] of agendaMap) {
    agendas.push({
      id: `agenda-${order}`,
      topic,
      decisions: topicDecisions,
    });
    order++;
  }

  return agendas;
}

interface PRReviewState {
  // 상태
  meeting: MeetingWithParticipants | null;
  decisions: Decision[];
  agendas: PRAgenda[];
  prStatus: PRStatus | null;
  loading: boolean;
  error: string | null;
  actionLoading: Record<string, boolean>; // decisionId -> loading

  // 액션
  fetchMeetingReview: (meetingId: string) => Promise<void>;
  approveDecision: (decisionId: string) => Promise<DecisionReviewResponse | null>;
  rejectDecision: (decisionId: string) => Promise<DecisionReviewResponse | null>;
  clearError: () => void;
  reset: () => void;
}

export const usePRReviewStore = create<PRReviewState>((set) => ({
  // 초기 상태
  meeting: null,
  decisions: [],
  agendas: [],
  prStatus: null,
  loading: false,
  error: null,
  actionLoading: {},

  // 회의 정보와 결정사항 목록 조회
  fetchMeetingReview: async (meetingId: string) => {
    set({ loading: true, error: null });
    try {
      // 회의 정보와 결정사항 병렬 조회
      const [meeting, { decisions }] = await Promise.all([
        meetingService.getMeeting(meetingId),
        prReviewService.getMeetingDecisions(meetingId),
      ]);

      const agendas = groupDecisionsByAgenda(decisions);
      const prStatus = calculatePRStatus(meetingId, decisions);

      set({ meeting, decisions, agendas, prStatus, loading: false });
    } catch (error) {
      const message = getErrorMessage(error, '회의 정보를 불러오는데 실패했습니다.');
      set({ error: message, loading: false });
    }
  },

  // 결정 승인
  approveDecision: async (decisionId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [decisionId]: true },
    }));
    try {
      const response = await prReviewService.approveDecision(decisionId);

      // 해당 결정사항 다시 조회하여 상태 업데이트
      const updatedDecision = await prReviewService.getDecision(decisionId);

      set((state) => {
        const updatedDecisions = state.decisions.map((d) =>
          d.id === decisionId ? updatedDecision : d
        );
        const agendas = groupDecisionsByAgenda(updatedDecisions);
        const prStatus = state.meeting
          ? calculatePRStatus(state.meeting.id, updatedDecisions)
          : null;

        return {
          decisions: updatedDecisions,
          agendas,
          prStatus,
          actionLoading: { ...state.actionLoading, [decisionId]: false },
        };
      });

      return response;
    } catch (error) {
      const message = getErrorMessage(error, '승인 처리에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [decisionId]: false },
      }));
      return null;
    }
  },

  // 결정 거절
  rejectDecision: async (decisionId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [decisionId]: true },
    }));
    try {
      const response = await prReviewService.rejectDecision(decisionId);

      // 해당 결정사항 다시 조회하여 상태 업데이트
      const updatedDecision = await prReviewService.getDecision(decisionId);

      set((state) => {
        const updatedDecisions = state.decisions.map((d) =>
          d.id === decisionId ? updatedDecision : d
        );
        const agendas = groupDecisionsByAgenda(updatedDecisions);
        const prStatus = state.meeting
          ? calculatePRStatus(state.meeting.id, updatedDecisions)
          : null;

        return {
          decisions: updatedDecisions,
          agendas,
          prStatus,
          actionLoading: { ...state.actionLoading, [decisionId]: false },
        };
      });

      return response;
    } catch (error) {
      const message = getErrorMessage(error, '거절 처리에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [decisionId]: false },
      }));
      return null;
    }
  },

  // 에러 클리어
  clearError: () => set({ error: null }),

  // 상태 초기화
  reset: () =>
    set({
      meeting: null,
      decisions: [],
      agendas: [],
      prStatus: null,
      loading: false,
      error: null,
      actionLoading: {},
    }),
}));
