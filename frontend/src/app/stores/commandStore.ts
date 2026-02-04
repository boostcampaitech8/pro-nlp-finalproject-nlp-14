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

  // 세션 Actions
  setCurrentSession: (id: string | null) => void;
  loadSessionMessages: (id: string) => Promise<void>;
  setSessions: (sessions: SpotlightSession[]) => void;
  addSession: (session: SpotlightSession) => void;
  removeSession: (id: string) => void;
  loadSessions: () => Promise<void>;
  createNewSession: () => Promise<SpotlightSession | null>;
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
    set({ isChatMode: false, chatMessages: [], isStreaming: false }),

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

  // 세션 Actions
  setCurrentSession: (id) => {
    set({ currentSessionId: id, chatMessages: [] });
  },

  loadSessionMessages: async (id) => {
    set({ messagesLoading: true });
    try {
      const messages = await spotlightApi.getSessionMessages(id);
      const chatMessages = messages.map((msg, index) => ({
        id: `history-${id}-${index}`,
        role: msg.role === 'user' ? 'user' : 'agent',
        content: msg.content,
        timestamp: new Date(),
      })) as ChatMessage[];
      set({ chatMessages, messagesLoading: false });
    } catch (error) {
      console.error('Failed to load session messages:', error);
      set({ messagesLoading: false });
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
}));
