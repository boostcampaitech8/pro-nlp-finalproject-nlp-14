/**
 * KG (Knowledge Graph) Store
 *
 * Minutes, Comments, Suggestions, ActionItems 상태 관리
 */

import type {
  ActionItem,
  Comment,
  DecisionReviewResponse,
  DecisionWithReview,
  MinutesResponse,
  PRStatus,
  Suggestion,
  UpdateActionItemRequest,
  UpdateAgendaRequest,
} from '@/types';
import type { DecisionStatus } from '@/types/kg';
import axios from 'axios';
import { create } from 'zustand';

import { kgService } from '@/services/kgService';

// API 에러에서 사용자 친화적 메시지 추출
function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error) && error.response?.data) {
    const data = error.response.data;
    if (data.detail?.message) {
      return data.detail.message;
    }
    if (data.message) {
      return data.message;
    }
  }
  return fallback;
}

// 깊은 복사로 minutes 내 특정 decision 업데이트
function updateDecisionInMinutes(
  minutes: MinutesResponse,
  decisionId: string,
  updater: (decision: DecisionWithReview) => DecisionWithReview
): MinutesResponse {
  return {
    ...minutes,
    agendas: minutes.agendas.map((agenda) => ({
      ...agenda,
      decisions: agenda.decisions.map((decision) =>
        decision.id === decisionId ? updater(decision) : decision
      ),
    })),
  };
}

// Comment를 중첩 구조에서 삭제
function removeCommentFromTree(comments: Comment[], commentId: string): Comment[] {
  return comments
    .filter((c) => c.id !== commentId)
    .map((c) => ({
      ...c,
      replies: removeCommentFromTree(c.replies, commentId),
    }));
}

// Comment를 중첩 구조에 추가 (parentId가 있으면 해당 댓글의 replies에 추가)
function addCommentToTree(
  comments: Comment[],
  newComment: Comment,
  parentId?: string
): Comment[] {
  if (!parentId) {
    return [...comments, newComment];
  }
  return comments.map((c) => {
    if (c.id === parentId) {
      return { ...c, replies: [...c.replies, newComment] };
    }
    return { ...c, replies: addCommentToTree(c.replies, newComment, parentId) };
  });
}

interface KGState {
  // Minutes 상태
  minutes: MinutesResponse | null;
  minutesLoading: boolean;
  minutesError: string | null;

  // PR 상태 (Minutes 데이터에서 계산)
  prStatus: PRStatus | null;

  // ActionItems 상태 (별도 목록)
  actionItems: ActionItem[];
  actionItemsLoading: boolean;

  // 개별 액션 로딩 상태
  actionLoading: Record<string, boolean>;

  // 일반 에러
  error: string | null;

  // === Minutes 액션 ===
  fetchMinutes: (meetingId: string) => Promise<void>;
  refreshMinutes: () => Promise<void>;

  // === Comment 액션 ===
  addComment: (decisionId: string, content: string) => Promise<Comment | null>;
  addReply: (
    commentId: string,
    decisionId: string,
    content: string
  ) => Promise<Comment | null>;
  removeComment: (commentId: string, decisionId: string) => Promise<boolean>;

  // === Suggestion 액션 ===
  addSuggestion: (decisionId: string, content: string, meetingId: string) => Promise<Suggestion | null>;

  // === Agenda 액션 ===
  updateAgenda: (agendaId: string, data: UpdateAgendaRequest) => Promise<boolean>;
  removeAgenda: (agendaId: string) => Promise<boolean>;

  // === Decision 액션 ===
  updateDecision: (
    decisionId: string,
    data: { content?: string; context?: string }
  ) => Promise<boolean>;
  approveDecision: (decisionId: string) => Promise<DecisionReviewResponse | null>;
  rejectDecision: (decisionId: string) => Promise<DecisionReviewResponse | null>;

  // === PR 상태 ===
  isAllDecisionsLatest: () => boolean;

  // === ActionItem 액션 ===
  fetchActionItems: (filters?: { assigneeId?: string; status?: string }) => Promise<void>;
  updateActionItem: (
    actionItemId: string,
    data: UpdateActionItemRequest
  ) => Promise<boolean>;
  removeActionItem: (actionItemId: string) => Promise<boolean>;

  // === 유틸리티 ===
  clearError: () => void;
  reset: () => void;
}

export const useKGStore = create<KGState>((set, get) => ({
  // 초기 상태
  minutes: null,
  minutesLoading: false,
  minutesError: null,
  prStatus: null,
  actionItems: [],
  actionItemsLoading: false,
  actionLoading: {},
  error: null,

  // === Minutes 액션 ===

  fetchMinutes: async (meetingId: string) => {
    set({ minutesLoading: true, minutesError: null });
    try {
      const minutes = await kgService.getMinutes(meetingId);
      const prStatus = kgService.calculatePRStatus(minutes);
      set({ minutes, prStatus, minutesLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, '회의록을 불러오는데 실패했습니다.');
      set({ minutesError: message, minutesLoading: false });
    }
  },

  refreshMinutes: async () => {
    const { minutes } = get();
    if (minutes) {
      await get().fetchMinutes(minutes.meetingId);
    }
  },

  // === Comment 액션 ===

  addComment: async (decisionId: string, content: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`comment-${decisionId}`]: true },
    }));
    try {
      const comment = await kgService.createComment(decisionId, content);

      // 로컬 상태 업데이트
      set((state) => {
        if (!state.minutes) return state;
        const newMinutes = updateDecisionInMinutes(state.minutes, decisionId, (d) => ({
          ...d,
          comments: [...d.comments, comment],
        }));
        return {
          minutes: newMinutes,
          actionLoading: { ...state.actionLoading, [`comment-${decisionId}`]: false },
        };
      });

      return comment;
    } catch (error) {
      const message = getErrorMessage(error, '댓글 작성에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`comment-${decisionId}`]: false },
      }));
      return null;
    }
  },

  addReply: async (commentId: string, decisionId: string, content: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`reply-${commentId}`]: true },
    }));
    try {
      const reply = await kgService.createReply(commentId, content);

      // 로컬 상태 업데이트
      set((state) => {
        if (!state.minutes) return state;
        const newMinutes = updateDecisionInMinutes(state.minutes, decisionId, (d) => ({
          ...d,
          comments: addCommentToTree(d.comments, reply, commentId),
        }));
        return {
          minutes: newMinutes,
          actionLoading: { ...state.actionLoading, [`reply-${commentId}`]: false },
        };
      });

      return reply;
    } catch (error) {
      const message = getErrorMessage(error, '답글 작성에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`reply-${commentId}`]: false },
      }));
      return null;
    }
  },

  removeComment: async (commentId: string, decisionId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`delete-${commentId}`]: true },
    }));
    try {
      await kgService.deleteComment(commentId);

      // 로컬 상태 업데이트
      set((state) => {
        if (!state.minutes) return state;
        const newMinutes = updateDecisionInMinutes(state.minutes, decisionId, (d) => ({
          ...d,
          comments: removeCommentFromTree(d.comments, commentId),
        }));
        return {
          minutes: newMinutes,
          actionLoading: { ...state.actionLoading, [`delete-${commentId}`]: false },
        };
      });

      return true;
    } catch (error) {
      const message = getErrorMessage(error, '댓글 삭제에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`delete-${commentId}`]: false },
      }));
      return false;
    }
  },

  // === Suggestion 액션 ===

  addSuggestion: async (decisionId: string, content: string, meetingId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`suggestion-${decisionId}`]: true },
    }));
    try {
      const suggestion = await kgService.createSuggestion(decisionId, content, meetingId);

      // 전체 새로고침으로 새 Decision + superseded 상태 반영
      await get().refreshMinutes();

      set((state) => ({
        actionLoading: { ...state.actionLoading, [`suggestion-${decisionId}`]: false },
      }));
      return suggestion;
    } catch (error) {
      const message = getErrorMessage(error, '제안 작성에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`suggestion-${decisionId}`]: false },
      }));
      return null;
    }
  },

  // === Agenda 액션 ===

  updateAgenda: async (agendaId: string, data: UpdateAgendaRequest) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`agenda-${agendaId}`]: true },
    }));
    try {
      const updatedAgenda = await kgService.updateAgenda(agendaId, data);

      set((state) => {
        if (!state.minutes) return state;
        return {
          minutes: {
            ...state.minutes,
            agendas: state.minutes.agendas.map((a) =>
              a.id === agendaId ? { ...a, ...updatedAgenda } : a
            ),
          },
          actionLoading: { ...state.actionLoading, [`agenda-${agendaId}`]: false },
        };
      });

      return true;
    } catch (error) {
      const message = getErrorMessage(error, '안건 수정에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`agenda-${agendaId}`]: false },
      }));
      return false;
    }
  },

  removeAgenda: async (agendaId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`delete-agenda-${agendaId}`]: true },
    }));
    try {
      await kgService.deleteAgenda(agendaId);

      set((state) => {
        if (!state.minutes) return state;
        return {
          minutes: {
            ...state.minutes,
            agendas: state.minutes.agendas.filter((a) => a.id !== agendaId),
          },
          actionLoading: { ...state.actionLoading, [`delete-agenda-${agendaId}`]: false },
        };
      });

      return true;
    } catch (error) {
      const message = getErrorMessage(error, '안건 삭제에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`delete-agenda-${agendaId}`]: false },
      }));
      return false;
    }
  },

  // === Decision 액션 ===

  updateDecision: async (
    decisionId: string,
    data: { content?: string; context?: string }
  ) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`decision-${decisionId}`]: true },
    }));
    try {
      await kgService.updateDecision(decisionId, data);

      set((state) => {
        if (!state.minutes) return state;
        const newMinutes = updateDecisionInMinutes(state.minutes, decisionId, (d) => ({
          ...d,
          ...data,
        }));
        return {
          minutes: newMinutes,
          actionLoading: { ...state.actionLoading, [`decision-${decisionId}`]: false },
        };
      });

      return true;
    } catch (error) {
      const message = getErrorMessage(error, '결정 수정에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`decision-${decisionId}`]: false },
      }));
      return false;
    }
  },

  approveDecision: async (decisionId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`approve-${decisionId}`]: true },
    }));
    try {
      const result = await kgService.approveDecision(decisionId);

      // 로컬 상태 업데이트 - 승인자 추가 및 상태 업데이트
      set((state) => {
        if (!state.minutes) return state;
        const newMinutes = updateDecisionInMinutes(state.minutes, decisionId, (d) => ({
          ...d,
          status: result.status as DecisionStatus,
          approvers: [...new Set([...d.approvers, 'currentUser'])], // 임시: 실제 userId 필요
        }));
        const prStatus = kgService.calculatePRStatus(newMinutes);
        return {
          minutes: newMinutes,
          prStatus,
          actionLoading: { ...state.actionLoading, [`approve-${decisionId}`]: false },
        };
      });

      // 전체 새로고침 (정확한 상태 동기화)
      await get().refreshMinutes();

      return result;
    } catch (error) {
      const message = getErrorMessage(error, '결정 승인에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`approve-${decisionId}`]: false },
      }));
      return null;
    }
  },

  rejectDecision: async (decisionId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`reject-${decisionId}`]: true },
    }));
    try {
      const result = await kgService.rejectDecision(decisionId);

      // 로컬 상태 업데이트 - 거절자 추가 및 상태 업데이트
      set((state) => {
        if (!state.minutes) return state;
        const newMinutes = updateDecisionInMinutes(state.minutes, decisionId, (d) => ({
          ...d,
          status: result.status as DecisionStatus,
          rejectors: [...new Set([...d.rejectors, 'currentUser'])], // 임시: 실제 userId 필요
        }));
        const prStatus = kgService.calculatePRStatus(newMinutes);
        return {
          minutes: newMinutes,
          prStatus,
          actionLoading: { ...state.actionLoading, [`reject-${decisionId}`]: false },
        };
      });

      // 전체 새로고침 (정확한 상태 동기화)
      await get().refreshMinutes();

      return result;
    } catch (error) {
      const message = getErrorMessage(error, '결정 거절에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`reject-${decisionId}`]: false },
      }));
      return null;
    }
  },

  // === PR 상태 ===

  isAllDecisionsLatest: () => {
    const { minutes } = get();
    if (!minutes) return false;
    return kgService.isAllDecisionsLatest(minutes);
  },

  // === ActionItem 액션 ===

  fetchActionItems: async (filters) => {
    set({ actionItemsLoading: true });
    try {
      const actionItems = await kgService.getActionItems(filters);
      set({ actionItems, actionItemsLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, '액션 아이템을 불러오는데 실패했습니다.');
      set({ error: message, actionItemsLoading: false });
    }
  },

  updateActionItem: async (actionItemId: string, data: UpdateActionItemRequest) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`actionitem-${actionItemId}`]: true },
    }));
    try {
      const updated = await kgService.updateActionItem(actionItemId, data);

      set((state) => {
        // actionItems 목록 업데이트
        const newActionItems = state.actionItems.map((item) =>
          item.id === actionItemId ? updated : item
        );

        // minutes 내 actionItems도 업데이트
        let newMinutes = state.minutes;
        if (newMinutes) {
          newMinutes = {
            ...newMinutes,
            actionItems: newMinutes.actionItems.map((item) =>
              item.id === actionItemId ? updated : item
            ),
          };
        }

        return {
          actionItems: newActionItems,
          minutes: newMinutes,
          actionLoading: { ...state.actionLoading, [`actionitem-${actionItemId}`]: false },
        };
      });

      return true;
    } catch (error) {
      const message = getErrorMessage(error, '액션 아이템 수정에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: { ...state.actionLoading, [`actionitem-${actionItemId}`]: false },
      }));
      return false;
    }
  },

  removeActionItem: async (actionItemId: string) => {
    set((state) => ({
      actionLoading: { ...state.actionLoading, [`delete-actionitem-${actionItemId}`]: true },
    }));
    try {
      await kgService.deleteActionItem(actionItemId);

      set((state) => {
        const newActionItems = state.actionItems.filter((item) => item.id !== actionItemId);

        let newMinutes = state.minutes;
        if (newMinutes) {
          newMinutes = {
            ...newMinutes,
            actionItems: newMinutes.actionItems.filter((item) => item.id !== actionItemId),
          };
        }

        return {
          actionItems: newActionItems,
          minutes: newMinutes,
          actionLoading: {
            ...state.actionLoading,
            [`delete-actionitem-${actionItemId}`]: false,
          },
        };
      });

      return true;
    } catch (error) {
      const message = getErrorMessage(error, '액션 아이템 삭제에 실패했습니다.');
      set((state) => ({
        error: message,
        actionLoading: {
          ...state.actionLoading,
          [`delete-actionitem-${actionItemId}`]: false,
        },
      }));
      return false;
    }
  },

  // === 유틸리티 ===

  clearError: () => set({ error: null, minutesError: null }),

  reset: () =>
    set({
      minutes: null,
      minutesLoading: false,
      minutesError: null,
      prStatus: null,
      actionItems: [],
      actionItemsLoading: false,
      actionLoading: {},
      error: null,
    }),
}));
