// 명령 처리 훅
import { useCallback } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { agentService } from '@/app/services/agentService';
import type { HistoryItem } from '@/app/types/command';

export function useCommand() {
  const {
    inputValue,
    activeCommand,
    setInputValue,
    setProcessing,
    setActiveCommand,
    updateField,
    addHistory,
    clearActiveCommand,
  } = useCommandStore();

  const { openModal: openMeetingModal } = useMeetingModalStore();

  // 명령 제출
  const submitCommand = useCallback(
    async (command?: string) => {
      const cmd = command || inputValue;
      if (!cmd.trim()) return;

      setProcessing(true);
      setInputValue('');

      try {
        // agentService를 통해 명령 처리
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
          // 직접 결과 표시
          const historyItem: HistoryItem = {
            id: `history-${Date.now()}`,
            command: cmd,
            result: response.message || '완료',
            timestamp: new Date(),
            icon: '✅',
            status: 'success',
          };
          addHistory(historyItem);
        }
      } catch (error) {
        // 에러 처리
        const historyItem: HistoryItem = {
          id: `history-${Date.now()}`,
          command: cmd,
          result: '명령 처리 중 오류가 발생했습니다.',
          timestamp: new Date(),
          icon: '❌',
          status: 'error',
        };
        addHistory(historyItem);
        console.error('Command processing error:', error);
      } finally {
        setProcessing(false);
      }
    },
    [inputValue, setInputValue, setProcessing, setActiveCommand, addHistory, openMeetingModal]
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
        icon: activeCommand.icon || '✅',
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
        icon: '❌',
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
    setInputValue,
    submitCommand,
    submitForm,
    cancelCommand,
    updateField,
  };
}
