// 대화 모드 전용 명령 처리 훅
import { useState, useCallback } from 'react';
import { useConversationStore } from '@/app/stores/conversationStore';
import { useCommandStore } from '@/app/stores/commandStore';
import { usePreviewStore, type PreviewType } from '@/app/stores/previewStore';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { agentService } from '@/app/services/agentService';
import type { HistoryItem } from '@/app/types/command';

// 유효한 프리뷰 타입 목록
const VALID_PREVIEW_TYPES: PreviewType[] = ['meeting', 'document', 'command-result', 'search-result', 'timeline', 'action-items', 'branch-diff'];

function isValidPreviewType(type: string): type is PreviewType {
  return VALID_PREVIEW_TYPES.includes(type as PreviewType);
}

export function useConversationCommand() {
  const [isProcessing, setIsProcessing] = useState(false);

  const {
    addMessage,
    updateLastAgentMessage,
    setPendingForm,
    pendingForm,
    endConversation,
  } = useConversationStore();

  const { sessionContext, addHistory } = useCommandStore();
  const { setPreview } = usePreviewStore();
  const { openModal: openMeetingModal } = useMeetingModalStore();

  // 명령 제출
  const submitCommand = useCallback(
    async (command: string) => {
      if (!command.trim() || isProcessing) return;

      setIsProcessing(true);

      // 1. 사용자 메시지 추가
      addMessage({ type: 'user', content: command });

      // 2. 로딩 메시지 추가
      addMessage({
        type: 'agent',
        content: '',
        agentData: { responseType: 'loading' },
      });

      try {
        // 3. agentService 호출
        const response = await agentService.processCommand(command, sessionContext);

        // 4. 응답 타입별 처리
        if (response.type === 'modal' && response.modalData) {
          // 모달 표시 (대화 모드에서도 모달 사용)
          if (response.modalData.modalType === 'meeting') {
            openMeetingModal({
              title: response.modalData.title,
              description: response.modalData.description,
              scheduledAt: response.modalData.scheduledAt,
              teamId: response.modalData.teamId,
            });
          }
          updateLastAgentMessage({
            content: '회의 생성 모달이 열렸습니다.',
            agentData: { responseType: 'text' },
          });
        } else if (response.type === 'form' && response.command) {
          // Form 표시
          setPendingForm(response.command);
          updateLastAgentMessage({
            content: response.command.description || '아래 폼을 작성해주세요.',
            agentData: {
              responseType: 'form',
              form: response.command,
            },
          });
        } else {
          // 직접 결과 표시
          updateLastAgentMessage({
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

          // 프리뷰 패널 업데이트
          if (response.previewData) {
            const previewType = response.previewData.type;
            if (isValidPreviewType(previewType)) {
              setPreview(previewType, {
                title: response.previewData.title,
                content: response.previewData.content,
                createdAt: new Date().toISOString(),
              });
            } else {
              setPreview('command-result', {
                title: response.previewData.title,
                content: response.previewData.content,
                createdAt: new Date().toISOString(),
              });
            }
          }

          // 히스토리에도 추가
          const historyItem: HistoryItem = {
            id: `history-${Date.now()}`,
            command,
            result: response.message || '완료',
            timestamp: new Date(),
            icon: '✅',
            status: 'success',
          };
          addHistory(historyItem);
        }
      } catch (error) {
        // 에러 처리
        updateLastAgentMessage({
          content: '명령 처리 중 오류가 발생했습니다.',
          agentData: { responseType: 'text' },
        });
        console.error('Conversation command error:', error);
      } finally {
        setIsProcessing(false);
      }
    },
    [isProcessing, sessionContext, addMessage, updateLastAgentMessage, setPendingForm, setPreview, addHistory, openMeetingModal]
  );

  // Form 제출
  const submitForm = useCallback(async () => {
    if (!pendingForm || isProcessing) return;

    setIsProcessing(true);

    // 폼 필드 값 추출
    const fieldValues: Record<string, string> = {};
    const fieldSummary: Record<string, string> = {};
    pendingForm.fields.forEach((f) => {
      if (f.value) {
        fieldValues[f.id] = f.value;
        fieldSummary[f.label] = f.value;
      }
    });

    // 사용자 메시지로 폼 제출 표시
    addMessage({
      type: 'user',
      content: `${pendingForm.title} 제출`,
      userData: { formSummary: fieldSummary },
    });

    // 로딩 표시
    addMessage({
      type: 'agent',
      content: '',
      agentData: { responseType: 'loading' },
    });

    try {
      const response = await agentService.submitForm(
        pendingForm.id,
        pendingForm.title,
        fieldValues
      );

      updateLastAgentMessage({
        content: response.message || `${pendingForm.title} 완료`,
        agentData: {
          responseType: 'result',
          previewData: response.previewData ? {
            title: response.previewData.title,
            content: response.previewData.content,
          } : undefined,
        },
      });

      // 프리뷰 업데이트
      if (response.previewData) {
        setPreview('command-result', {
          title: response.previewData.title,
          content: response.previewData.content,
          createdAt: new Date().toISOString(),
        });
      }

      // 히스토리 추가
      const historyItem: HistoryItem = {
        id: `history-${Date.now()}`,
        command: pendingForm.title,
        result: response.message || `${pendingForm.title} 완료`,
        timestamp: new Date(),
        icon: pendingForm.icon || '✅',
        status: 'success',
      };
      addHistory(historyItem);

      setPendingForm(null);
    } catch (error) {
      updateLastAgentMessage({
        content: '폼 제출 중 오류가 발생했습니다.',
        agentData: { responseType: 'text' },
      });
      console.error('Form submission error:', error);
    } finally {
      setIsProcessing(false);
    }
  }, [pendingForm, isProcessing, addMessage, updateLastAgentMessage, setPendingForm, setPreview, addHistory]);

  // Form 취소
  const cancelForm = useCallback(() => {
    setPendingForm(null);
    // 마지막 에이전트 메시지의 폼 제거
    updateLastAgentMessage({
      content: '폼이 취소되었습니다.',
      agentData: { responseType: 'text', form: undefined },
    });
  }, [setPendingForm, updateLastAgentMessage]);

  // Form 필드 업데이트
  const updateFormField = useCallback(
    (fieldId: string, value: string) => {
      if (!pendingForm) return;

      const updatedForm = {
        ...pendingForm,
        fields: pendingForm.fields.map((f) =>
          f.id === fieldId ? { ...f, value } : f
        ),
      };
      setPendingForm(updatedForm);

      // 에이전트 메시지의 폼도 업데이트
      updateLastAgentMessage({
        agentData: { form: updatedForm },
      });
    },
    [pendingForm, setPendingForm, updateLastAgentMessage]
  );

  return {
    submitCommand,
    submitForm,
    cancelForm,
    updateFormField,
    isProcessing,
    endConversation,
  };
}
