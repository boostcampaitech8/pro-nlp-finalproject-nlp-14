// 명령 상태 관리 스토어
import { create } from 'zustand';
import { HISTORY_LIMIT } from '@/app/constants';
import type { ActiveCommand, ChatMessage, HistoryItem, Suggestion } from '@/app/types/command';

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
  setStreaming: (streaming: boolean) => void;
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

  setStreaming: (streaming) => set({ isStreaming: streaming }),
}));
