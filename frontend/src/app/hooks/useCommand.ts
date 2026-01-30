// 명령 처리 훅
import { useCallback } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { agentService } from '@/app/services/agentService';
import type { ChatMessage, HistoryItem } from '@/app/types/command';

export function useCommand() {
  const {
    inputValue,
    activeCommand,
    isChatMode,
    setInputValue,
    setProcessing,
    setActiveCommand,
    updateField,
    addHistory,
    clearActiveCommand,
    enterChatMode,
    exitChatMode,
    addChatMessage,
    setStreaming,
  } = useCommandStore();

  const { openModal: openMeetingModal } = useMeetingModalStore();

  // 채팅 메시지 전송 (에이전트 응답 요청 포함)
  const sendChatMessage = useCallback(
    async (text: string) => {
      // 사용자 메시지 추가
      const userMsg: ChatMessage = {
        id: `chat-${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: new Date(),
      };
      addChatMessage(userMsg);

      // 에이전트 응답 요청
      try {
        const response = await agentService.processChatMessage(text);
        const agentMsg: ChatMessage = {
          id: `chat-${Date.now()}-agent`,
          role: 'agent',
          content: response,
          timestamp: new Date(),
        };
        setStreaming(true);
        addChatMessage(agentMsg);
      } catch {
        const errorMsg: ChatMessage = {
          id: `chat-${Date.now()}-error`,
          role: 'agent',
          content: '응답 처리 중 오류가 발생했습니다. 다시 시도해주세요.',
          timestamp: new Date(),
        };
        setStreaming(true);
        addChatMessage(errorMsg);
      }
    },
    [addChatMessage, setStreaming]
  );

  // 명령 제출
  const submitCommand = useCallback(
    async (command?: string) => {
      const cmd = command || inputValue;
      if (!cmd.trim()) return;

      setInputValue('');

      // 채팅 모드: 메시지 전송
      if (isChatMode) {
        await sendChatMessage(cmd);
        return;
      }

      // 기존 명령 처리 로직 (채팅 모드가 아닌 경우)
      setProcessing(true);

      try {
        const response = await agentService.processCommand(cmd);

        if (response.type === 'modal' && response.modalData) {
          // 모달 표시
          if (response.modalData.modalType === 'meeting') {
            openMeetingModal({
              title: response.modalData.title,
              description: response.modalData.description,
              scheduledAt: response.modalData.scheduledAt,
              teamId: response.modalData.teamId,
            });
          }
        } else if (response.type === 'form' && response.command) {
          // Form 표시
          setActiveCommand(response.command);
        } else {
          // 채팅 모드 진입 (direct 응답)
          enterChatMode();
          // 사용자 메시지 + 에이전트 응답 추가
          const userMsg: ChatMessage = {
            id: `chat-${Date.now()}`,
            role: 'user',
            content: cmd,
            timestamp: new Date(),
          };
          addChatMessage(userMsg);

          // 에이전트 채팅 응답 요청
          try {
            const chatResponse = await agentService.processChatMessage(cmd);
            const agentMsg: ChatMessage = {
              id: `chat-${Date.now()}-agent`,
              role: 'agent',
              content: chatResponse,
              timestamp: new Date(),
            };
            setStreaming(true);
            addChatMessage(agentMsg);
          } catch {
            const errorMsg: ChatMessage = {
              id: `chat-${Date.now()}-error`,
              role: 'agent',
              content: '응답 처리 중 오류가 발생했습니다.',
              timestamp: new Date(),
            };
            setStreaming(true);
            addChatMessage(errorMsg);
          }
        }
      } catch (error) {
        // 에러 처리
        const historyItem: HistoryItem = {
          id: `history-${Date.now()}`,
          command: cmd,
          result: '명령 처리 중 오류가 발생했습니다.',
          timestamp: new Date(),
          icon: '---',
          status: 'error',
        };
        addHistory(historyItem);
        console.error('Command processing error:', error);
      } finally {
        setProcessing(false);
      }
    },
    [
      inputValue,
      isChatMode,
      setInputValue,
      setProcessing,
      setActiveCommand,
      addHistory,
      openMeetingModal,
      enterChatMode,
      addChatMessage,
      setStreaming,
      sendChatMessage,
    ]
  );

  // Form 제출
  const submitForm = useCallback(async () => {
    if (!activeCommand) return;

    setProcessing(true);

    try {
      // 필드 값 추출 (id를 키로 사용하여 i18n 호환성 확보)
      const fieldValues: Record<string, string> = {};
      activeCommand.fields.forEach((f) => {
        if (f.value) {
          fieldValues[f.id] = f.value;
        }
      });

      // agentService를 통해 Form 제출
      const response = await agentService.submitForm(
        activeCommand.id,
        activeCommand.title,
        fieldValues
      );

      const historyItem: HistoryItem = {
        id: `history-${Date.now()}`,
        command: activeCommand.title,
        result: response.message || `${activeCommand.title} 완료`,
        timestamp: new Date(),
        icon: activeCommand.icon || '---',
        status: 'success',
      };
      addHistory(historyItem);

      clearActiveCommand();
    } catch (error) {
      const historyItem: HistoryItem = {
        id: `history-${Date.now()}`,
        command: activeCommand.title,
        result: '명령 실행 중 오류가 발생했습니다.',
        timestamp: new Date(),
        icon: '---',
        status: 'error',
      };
      addHistory(historyItem);
      console.error('Form submission error:', error);
      clearActiveCommand();
    }
  }, [activeCommand, setProcessing, addHistory, clearActiveCommand]);

  // 명령 취소
  const cancelCommand = useCallback(() => {
    clearActiveCommand();
  }, [clearActiveCommand]);

  return {
    inputValue,
    activeCommand,
    isChatMode,
    setInputValue,
    submitCommand,
    submitForm,
    cancelCommand,
    updateField,
    exitChatMode,
  };
}
