// 명령 처리 훅
import { useCallback } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { spotlightApi, type SSEEvent } from '@/app/services/spotlightApi';
import type { ChatMessage } from '@/app/types/command';

export function useCommand() {
  const {
    inputValue,
    isChatMode,
    currentSessionId,
    setInputValue,
    setProcessing,
    enterChatMode,
    exitChatMode,
    addChatMessage,
    updateChatMessage,
    setStreaming,
    setStatusMessage,
    createNewSession,
  } = useCommandStore();

  // 채팅 메시지 전송 (세션 기반 SSE 스트림)
  const sendChatMessage = useCallback(
    async (text: string) => {
      // 세션이 없으면 새로 생성
      let sessionId = currentSessionId;
      if (!sessionId) {
        const session = await createNewSession();
        if (!session) {
          // 세션 생성 실패
          const errorMsg: ChatMessage = {
            id: `chat-${Date.now()}-error`,
            role: 'agent',
            content: '세션 생성에 실패했습니다. 다시 시도해주세요.',
            timestamp: new Date(),
          };
          addChatMessage(errorMsg);
          return;
        }
        sessionId = session.id;
      }

      // 사용자 메시지 추가
      const userMsg: ChatMessage = {
        id: `chat-${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: new Date(),
      };
      addChatMessage(userMsg);

      // 에이전트 응답 placeholder
      const agentMsgId = `chat-${Date.now()}-agent`;
      const agentMsg: ChatMessage = {
        id: agentMsgId,
        role: 'agent',
        type: 'text',
        content: '',
        timestamp: new Date(),
      };
      setStreaming(true);
      addChatMessage(agentMsg);

      // SSE 스트림 시작
      try {
        await spotlightApi.chatStreamWithRetry(sessionId, text, (event: SSEEvent) => {
          if (event.type === 'message' && event.data) {
            // 토큰 수신 시 상태 메시지 즉시 제거 + 토큰 누적
            setStatusMessage(null);
            updateChatMessage(agentMsgId, {
              content: (prev: string) => prev + event.data,
            });
          } else if (event.type === 'status' && event.data) {
            // 상태 메시지 (회색 텍스트로 덮어쓰기)
            setStatusMessage(event.data);
          } else if (event.type === 'done') {
            setStatusMessage(null); // 완료 시 상태 메시지 제거
            setStreaming(false);
          } else if (event.type === 'error') {
            setStatusMessage(null); // 에러 시 상태 메시지 제거
            updateChatMessage(agentMsgId, {
              content: event.error || '응답 처리 중 오류가 발생했습니다.',
            });
            setStreaming(false);
          }
        });
      } catch (error) {
        setStatusMessage(null);
        setStreaming(false);
        updateChatMessage(agentMsgId, {
          content: '응답 처리 중 오류가 발생했습니다. 다시 시도해주세요.',
        });
      }
    },
    [currentSessionId, createNewSession, addChatMessage, updateChatMessage, setStreaming, setStatusMessage]
  );

  // 명령 제출 (항상 Spotlight API 사용)
  const submitCommand = useCallback(
    async (command?: string) => {
      const cmd = command || inputValue;
      if (!cmd.trim()) return;

      setInputValue('');

      // 이미 채팅 모드 -> 후속 메시지 전송
      if (isChatMode) {
        await sendChatMessage(cmd);
        return;
      }

      // 채팅 모드 진입 후 첫 메시지도 Spotlight API로 전송
      setProcessing(true);
      enterChatMode();

      try {
        await sendChatMessage(cmd);
      } finally {
        setProcessing(false);
      }
    },
    [
      inputValue,
      isChatMode,
      setInputValue,
      setProcessing,
      enterChatMode,
      sendChatMessage,
    ]
  );

  // Plan 승인 (Spotlight API로 전송)
  const approvePlan = useCallback(
    async (messageId: string) => {
      // plan 메시지를 승인 상태로 업데이트
      updateChatMessage(messageId, { approved: true });

      // 승인 메시지를 Spotlight API로 전송
      await sendChatMessage('승인합니다');
    },
    [updateChatMessage, sendChatMessage]
  );

  return {
    inputValue,
    isChatMode,
    setInputValue,
    submitCommand,
    approvePlan,
    exitChatMode,
  };
}
