// 명령 상태 관리 스토어
import { create } from 'zustand';
import type { ActiveCommand, HistoryItem, Suggestion } from '@/app/types/command';

interface CommandState {
  // 상태
  inputValue: string;
  isInputFocused: boolean;
  isProcessing: boolean;
  activeCommand: ActiveCommand | null;
  history: HistoryItem[];
  suggestions: Suggestion[];

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
}

// 기본 추천 명령어
const defaultSuggestions: Suggestion[] = [
  {
    id: '1',
    title: '새 회의 시작',
    description: '팀원들과 새로운 회의를 시작합니다',
    icon: '🎯',
    command: '새 회의 시작',
    category: 'meeting',
  },
  {
    id: '2',
    title: '지난 회의록 검색',
    description: '이전 회의 내용을 검색합니다',
    icon: '🔍',
    command: '회의록 검색',
    category: 'search',
  },
  {
    id: '3',
    title: '오늘 일정 확인',
    description: '오늘 예정된 회의를 확인합니다',
    icon: '📅',
    command: '오늘 일정',
    category: 'action',
  },
  {
    id: '4',
    title: '팀 현황 보기',
    description: '팀 멤버와 활동 현황을 확인합니다',
    icon: '👥',
    command: '팀 현황',
    category: 'action',
  },
];

export const useCommandStore = create<CommandState>((set) => ({
  // 초기 상태
  inputValue: '',
  isInputFocused: false,
  isProcessing: false,
  activeCommand: null,
  history: [],
  suggestions: defaultSuggestions,

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
      history: [item, ...state.history].slice(0, 50), // 최대 50개
    })),

  clearHistory: () => set({ history: [] }),

  clearActiveCommand: () => set({ activeCommand: null, isProcessing: false }),

  setSuggestions: (suggestions) => set({ suggestions }),
}));
