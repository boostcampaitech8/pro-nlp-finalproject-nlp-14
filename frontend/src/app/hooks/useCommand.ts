// 명령 처리 훅
import { useCallback } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { usePreviewStore, type PreviewType } from '@/app/stores/previewStore';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { useConversationStore } from '@/app/stores/conversationStore';
import { agentService } from '@/app/services/agentService';
import { updatePreviewStore } from '@/app/utils/previewUtils';
import { createSuccessHistoryItem, createErrorHistoryItem } from '@/app/utils/historyUtils';

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

  const { setPreview } = usePreviewStore();
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

        // 스토어에서 최신 상태 직접 가져오기 (closure 문제 방지)
        const { isConversationActive: isActive, updateLastAgentMessage: updateAgent, setPendingForm: setForm } = useConversationStore.getState();

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
          // 대화 모드일 때 에이전트 메시지 업데이트
          if (isActive) {
            updateAgent({
              content: '회의 생성 모달이 열렸습니다.',
              agentData: { responseType: 'text' },
            });
          }
        } else if (response.type === 'form' && response.command) {
          // Form 표시
          if (isActive) {
            // 대화 모드에서는 conversation store 사용
            setForm(response.command);
            updateAgent({
              content: response.command.description || '아래 폼을 작성해주세요.',
              agentData: {
                responseType: 'form',
                form: response.command,
              },
            });
          } else {
            setActiveCommand(response.command);
          }
        } else {
          // 직접 결과 표시
          addHistory(createSuccessHistoryItem(cmd, response.message || '완료'));

          // 대화 모드일 때 에이전트 메시지 업데이트
          if (isActive) {
            updateAgent({
              content: response.message || '완료되었습니다.',
              agentData: {
                responseType: 'result',
                previewType: response.previewData?.type as PreviewType,
                previewData: response.previewData ? {
                  title: response.previewData.title,
                  content: response.previewData.content,
                } : undefined,
              },
            });
          }

          // 프리뷰 패널 업데이트
          if (response.previewData) {
            updatePreviewStore(setPreview, response.previewData);
          }
        }
      } catch (error) {
        // 에러 처리
        addHistory(createErrorHistoryItem(cmd));

        // 대화 모드일 때 에러 메시지 추가 (최신 상태 가져오기)
        const { isConversationActive: isActive, updateLastAgentMessage: updateAgent } = useConversationStore.getState();
        if (isActive) {
          updateAgent({
            content: '명령 처리 중 오류가 발생했습니다.',
            agentData: { responseType: 'text' },
          });
        }

        console.error('Command processing error:', error);
      } finally {
        setProcessing(false);
      }
    },
    [inputValue, setInputValue, setProcessing, setActiveCommand, addHistory, setPreview, openMeetingModal]
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

      addHistory(createSuccessHistoryItem(
        activeCommand.title,
        response.message || `${activeCommand.title} 완료`,
        activeCommand.icon
      ));

      // 프리뷰 업데이트
      if (response.previewData) {
        updatePreviewStore(setPreview, {
          ...response.previewData,
          type: 'command-result',
        });
      }

      clearActiveCommand();
    } catch (error) {
      addHistory(createErrorHistoryItem(activeCommand.title, '명령 실행 중 오류가 발생했습니다.'));
      console.error('Form submission error:', error);
      clearActiveCommand();
    }
  }, [activeCommand, setProcessing, addHistory, setPreview, clearActiveCommand]);

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
