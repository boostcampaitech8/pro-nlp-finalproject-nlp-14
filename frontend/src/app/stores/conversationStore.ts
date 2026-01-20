// 대화 모드 상태 관리 스토어
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Message, LayoutMode, AgentMessageData } from '@/app/types/conversation';
import type { ActiveCommand } from '@/app/types/command';

// 에이전트 메시지 업데이트 파라미터
interface UpdateAgentMessageParams {
  content?: string;
  agentData?: Partial<AgentMessageData>;
}

interface ConversationState {
  // 상태
  isConversationActive: boolean;
  messages: Message[];
  pendingForm: ActiveCommand | null;
  layoutMode: LayoutMode;

  // Actions
  startConversation: () => void;
  endConversation: () => void;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateLastAgentMessage: (params: UpdateAgentMessageParams) => void;
  setPendingForm: (form: ActiveCommand | null) => void;
  clearMessages: () => void;
  setLayoutMode: (mode: LayoutMode) => void;
}

// 유니크 ID 생성
const generateId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

export const useConversationStore = create<ConversationState>()(
  persist(
    (set) => ({
      // 초기 상태
      isConversationActive: false,
      messages: [],
      pendingForm: null,
      layoutMode: 'fullscreen',

      // 대화 시작
      startConversation: () =>
        set({
          isConversationActive: true,
        }),

      // 대화 종료
      endConversation: () =>
        set({
          isConversationActive: false,
          messages: [],
          pendingForm: null,
        }),

      // 메시지 추가
      addMessage: (message) =>
        set((state) => ({
          messages: [
            ...state.messages,
            {
              ...message,
              id: generateId(),
              timestamp: new Date(),
            },
          ],
        })),

      // 마지막 에이전트 메시지 업데이트 (로딩 -> 결과)
      updateLastAgentMessage: ({ content, agentData }) =>
        set((state) => {
          const messages = [...state.messages];
          // 마지막 에이전트 메시지 찾기
          for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].type === 'agent') {
              messages[i] = {
                ...messages[i],
                // content가 제공되면 업데이트
                ...(content !== undefined && { content }),
                // agentData 병합
                agentData: {
                  ...messages[i].agentData,
                  ...agentData,
                } as AgentMessageData,
              };
              break;
            }
          }
          return { messages };
        }),

      // 폼 설정
      setPendingForm: (form) => set({ pendingForm: form }),

      // 메시지 초기화
      clearMessages: () => set({ messages: [], pendingForm: null }),

      // 레이아웃 모드 설정
      setLayoutMode: (mode) => set({ layoutMode: mode }),
    }),
    {
      name: 'mit-conversation-settings',
      // layoutMode만 persist
      partialize: (state) => ({ layoutMode: state.layoutMode }),
    }
  )
);
