// 명령 상태 관리 스토어
import { create } from 'zustand';
import { HISTORY_LIMIT } from '@/app/constants';
import type { ActiveCommand, ChatMessage, HistoryItem, Suggestion } from '@/app/types/command';
import { spotlightApi, SpotlightSession } from '@/app/services/spotlightApi';

interface CommandState {
  // 상태
  inputValue: string;
  isInputFocused: boolean;
  isProcessing: boolean;
  activeCommand: ActiveCommand | null;
  history: HistoryItem[];
  suggestions: Suggestion[];

  // 채팅 모드 상태
  isChatMode: boolean;
  chatMessages: ChatMessage[];
  isStreaming: boolean;
  statusMessage: string | null; // 현재 상태 메시지 (회색 텍스트로 표시)

  // 세션 상태
  currentSessionId: string | null;
  sessions: SpotlightSession[];
  sessionsLoading: boolean;
  messagesLoading: boolean;

  // SSE 스트림 관리 (세션 전환 시 cleanup용)
  currentAbortController: AbortController | null;

  // Actions
  setInputValue: (value: string) => void;
  setInputFocused: (focused: boolean) => void;
  setProcessing: (processing: boolean) => void;
  setActiveCommand: (command: ActiveCommand | null) => void;
  updateField: (fieldId: string, value: string) => void;
  addHistory: (item: HistoryItem) => void;
  clearHistory: () => void;
  clearActiveCommand: () => void;
  setSuggestions: (suggestions: Suggestion[]) => void;

  // 채팅 모드 Actions
  enterChatMode: () => void;
  exitChatMode: () => void;
  addChatMessage: (msg: ChatMessage) => void;
  updateChatMessage: (
    id: string,
    updates: Partial<Omit<ChatMessage, 'content'>> & { content?: string | ((prev: string) => string) }
  ) => void;
  setStreaming: (streaming: boolean) => void;
  setStatusMessage: (message: string | null) => void;

  // SSE 스트림 관리 Actions
  setAbortController: (controller: AbortController | null) => void;
  abortCurrentStream: () => void;

  // 세션 Actions
  setCurrentSession: (id: string | null) => void;
  loadSessionMessages: (id: string) => Promise<void>;
  syncSessionMessages: (id: string) => Promise<void>;
  setSessions: (sessions: SpotlightSession[]) => void;
  addSession: (session: SpotlightSession) => void;
  removeSession: (id: string) => void;
  loadSessions: () => Promise<void>;
  createNewSession: () => Promise<SpotlightSession | null>;

  // 새 응답이 있는 세션 표시
  sessionsWithNewResponse: Set<string>;
  markSessionNewResponse: (sessionId: string) => void;
  clearSessionNewResponse: (sessionId: string) => void;
}

export const useCommandStore = create<CommandState>((set) => ({
  // 초기 상태
  inputValue: '',
  isInputFocused: false,
  isProcessing: false,
  activeCommand: null,
  history: [],
  suggestions: [], // agentService.getSuggestions()로 로드

  // 채팅 모드 초기 상태
  isChatMode: false,
  chatMessages: [],
  isStreaming: false,
  statusMessage: null,

  // 세션 초기 상태
  currentSessionId: null,
  sessions: [],
  sessionsLoading: false,
  messagesLoading: false,

  // SSE 스트림 관리 초기 상태
  currentAbortController: null,

  // 새 응답이 있는 세션 초기 상태
  sessionsWithNewResponse: new Set<string>(),

  // Actions
  setInputValue: (value) => set({ inputValue: value }),

  setInputFocused: (focused) => set({ isInputFocused: focused }),

  setProcessing: (processing) => set({ isProcessing: processing }),

  setActiveCommand: (command) => set({ activeCommand: command }),

  updateField: (fieldId, value) =>
    set((state) => ({
      activeCommand: state.activeCommand
        ? {
            ...state.activeCommand,
            fields: state.activeCommand.fields.map((f) =>
              f.id === fieldId ? { ...f, value } : f
            ),
          }
        : null,
    })),

  addHistory: (item) =>
    set((state) => ({
      history: [item, ...state.history].slice(0, HISTORY_LIMIT),
    })),

  clearHistory: () => set({ history: [] }),

  clearActiveCommand: () => set({ activeCommand: null, isProcessing: false }),

  setSuggestions: (suggestions) => set({ suggestions }),

  // 채팅 모드 Actions
  enterChatMode: () => set({ isChatMode: true, chatMessages: [] }),

  exitChatMode: () =>
    set({ isChatMode: false, chatMessages: [], isStreaming: false, currentSessionId: null }),

  addChatMessage: (msg) =>
    set((state) => ({ chatMessages: [...state.chatMessages, msg] })),

  updateChatMessage: (id, updates) =>
    set((state) => ({
      chatMessages: state.chatMessages.map((msg): ChatMessage => {
        if (msg.id !== id) return msg;

        // Handle content update with function
        if ('content' in updates && typeof updates.content === 'function') {
          const contentUpdater = updates.content;
          return {
            ...msg,
            content: contentUpdater(msg.content),
          };
        }

        return { ...msg, ...updates } as ChatMessage;
      }),
    })),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setStatusMessage: (message) => set({ statusMessage: message }),

  // SSE 스트림 관리 Actions
  setAbortController: (controller) => set({ currentAbortController: controller }),

  abortCurrentStream: () =>
    set((state) => {
      if (state.currentAbortController) {
        state.currentAbortController.abort();
      }
      return {
        currentAbortController: null,
        isStreaming: false,
        statusMessage: null,
      };
    }),

  // 세션 Actions
  setCurrentSession: (id) => {
    // 기존 스트림 정리 후 세션 전환
    set((state) => {
      if (state.currentAbortController) {
        state.currentAbortController.abort();
      }
      // 새 응답 표시 제거
      const newSet = new Set(state.sessionsWithNewResponse);
      if (id) newSet.delete(id);
      return {
        currentSessionId: id,
        chatMessages: [],
        currentAbortController: null,
        isStreaming: false,
        statusMessage: null,
        sessionsWithNewResponse: newSet,
      };
    });
  },

  loadSessionMessages: async (id) => {
    set({ messagesLoading: true });
    try {
      const messages = await spotlightApi.getSessionMessages(id);
      const chatMessages = messages.map((msg, index) => {
        const baseMsg = {
          id: `history-${id}-${index}`,
          role: msg.role === 'user' ? 'user' : 'agent',
          content: msg.content,
          timestamp: new Date(),
        };

        // HITL 메시지 복원
        if (msg.type === 'hitl' && msg.hitl_data) {
          return {
            ...baseMsg,
            type: 'hitl' as const,
            hitlStatus: msg.hitl_status,
            hitlData: {
              tool_name: msg.hitl_data.tool_name,
              params: msg.hitl_data.params,
              params_display: msg.hitl_data.params_display,
              message: msg.hitl_data.message,
              required_fields: msg.hitl_data.required_fields,
              display_template: msg.hitl_data.display_template,
            },
          };
        }

        return { ...baseMsg, type: 'text' as const };
      }) as ChatMessage[];
      set({ chatMessages, messagesLoading: false });
    } catch (error) {
      console.error('Failed to load session messages:', error);
      set({ messagesLoading: false });
    }
  },

  syncSessionMessages: async (id) => {
    try {
      const messages = await spotlightApi.getSessionMessages(id);

      set((state) => {
        // 현재 세션이 아니면 무시
        if (state.currentSessionId !== id) return state;

        const serverMessages = messages.map((msg, index) => {
          const baseMsg = {
            id: `history-${id}-${index}`,
            role: msg.role === 'user' ? 'user' : 'agent',
            content: msg.content,
            timestamp: new Date(),
          };

          if (msg.type === 'hitl' && msg.hitl_data) {
            return {
              ...baseMsg,
              type: 'hitl' as const,
              hitlStatus: msg.hitl_status,
              hitlData: {
                tool_name: msg.hitl_data.tool_name,
                params: msg.hitl_data.params,
                params_display: msg.hitl_data.params_display,
                message: msg.hitl_data.message,
                required_fields: msg.hitl_data.required_fields,
                display_template: msg.hitl_data.display_template,
              },
            };
          }
          return { ...baseMsg, type: 'text' as const };
        }) as ChatMessage[];

        // 마지막 메시지 비교
        const lastLocal = state.chatMessages[state.chatMessages.length - 1];
        const lastServer = serverMessages[serverMessages.length - 1];

        // 서버 메시지가 더 많거나 내용이 다르면 새 응답으로 표시
        if (serverMessages.length > state.chatMessages.length ||
            (lastLocal && lastServer && lastLocal.content !== lastServer.content)) {
          // 현재 보고 있는 세션이 아닌 경우에만 새 응답 표시
          if (state.currentSessionId !== id) {
            return {
              chatMessages: serverMessages,
              sessionsWithNewResponse: new Set([...state.sessionsWithNewResponse, id]),
            };
          }
          return { chatMessages: serverMessages };
        }

        return state;
      });
    } catch (error) {
      console.error('Failed to sync session messages:', error);
    }
  },

  setSessions: (sessions) => set({ sessions }),

  addSession: (session) =>
    set((state) => ({ sessions: [session, ...state.sessions] })),

  removeSession: (id) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
      currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
    })),

  loadSessions: async () => {
    set({ sessionsLoading: true });
    try {
      const sessions = await spotlightApi.listSessions();
      set({ sessions, sessionsLoading: false });
    } catch (error) {
      const status = (error as { response?: { status?: number; data?: { error?: string } } })
        ?.response?.status;
      const errorCode = (error as { response?: { data?: { error?: string } } })
        ?.response?.data?.error;
      if (status === 404 && errorCode === 'DISABLED_IN_BETA') {
        set({ sessions: [], sessionsLoading: false });
        return;
      }
      console.error('Failed to load sessions:', error);
      set({ sessionsLoading: false });
    }
  },

  createNewSession: async () => {
    try {
      const session = await spotlightApi.createSession();
      set((state) => ({
        sessions: [session, ...state.sessions],
        currentSessionId: session.id,
        chatMessages: [],
        isChatMode: true,
      }));
      return session;
    } catch (error) {
      console.error('Failed to create session:', error);
      return null;
    }
  },

  // 새 응답 표시 Actions
  markSessionNewResponse: (sessionId) =>
    set((state) => ({
      sessionsWithNewResponse: new Set([...state.sessionsWithNewResponse, sessionId]),
    })),

  clearSessionNewResponse: (sessionId) =>
    set((state) => {
      const newSet = new Set(state.sessionsWithNewResponse);
      newSet.delete(sessionId);
      return { sessionsWithNewResponse: newSet };
    }),
}));
