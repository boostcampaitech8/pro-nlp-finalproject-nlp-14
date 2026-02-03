// 명령 처리 훅
import { useCallback } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { agentService } from '@/app/services/agentService';
import type { ChatMessage } from '@/app/types/command';

export function useCommand() {
  const {
    inputValue,
    isChatMode,
    setInputValue,
    setProcessing,
    enterChatMode,
    exitChatMode,
    addChatMessage,
    updateChatMessage,
    setStreaming,
  } = useCommandStore();

  // 채팅 메시지 전송 (후속 대화용 - 항상 text 응답)
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
          type: response.type,
          content: response.message,
          timestamp: new Date(),
        };
        setStreaming(true);
        addChatMessage(agentMsg);
        // 응답 완료 후 스트리밍 종료
        setStreaming(false);
      } catch {
        const errorMsg: ChatMessage = {
          id: `chat-${Date.now()}-error`,
          role: 'agent',
          content: '응답 처리 중 오류가 발생했습니다. 다시 시도해주세요.',
          timestamp: new Date(),
        };
        setStreaming(true);
        addChatMessage(errorMsg);
        setStreaming(false);
      }
    },
    [addChatMessage, setStreaming]
  );

  // 명령 제출 (항상 채팅 모드 진입)
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

      // 채팅 모드 진입
      setProcessing(true);

      try {
        enterChatMode();

        // 사용자 메시지 추가
        const userMsg: ChatMessage = {
          id: `chat-${Date.now()}`,
          role: 'user',
          content: cmd,
          timestamp: new Date(),
        };
        addChatMessage(userMsg);

        // 명령 처리 (text 또는 plan 응답)
        const response = await agentService.processCommand(cmd);

        // text 타입이면서 '채팅 모드로 전환합니다' 응답인 경우, 실제 채팅 응답을 요청
        if (response.type === 'text' && response.message === '채팅 모드로 전환합니다.') {
          const chatResponse = await agentService.processChatMessage(cmd);
          const agentMsg: ChatMessage = {
            id: `chat-${Date.now()}-agent`,
            role: 'agent',
            type: chatResponse.type,
            content: chatResponse.message,
            timestamp: new Date(),
          };
          setStreaming(true);
          addChatMessage(agentMsg);
          // 응답 완료 후 스트리밍 종료
          setStreaming(false);
        } else {
          // text 또는 plan 응답 추가
          const agentMsg: ChatMessage = {
            id: `chat-${Date.now()}-agent`,
            role: 'agent',
            type: response.type,
            content: response.message,
            timestamp: new Date(),
          };
          setStreaming(true);
          addChatMessage(agentMsg);
          // 응답 완료 후 스트리밍 종료
          setStreaming(false);
        }
      } catch (error) {
        const errorMsg: ChatMessage = {
          id: `chat-${Date.now()}-error`,
          role: 'agent',
          content: '명령 처리 중 오류가 발생했습니다.',
          timestamp: new Date(),
        };
        setStreaming(true);
        addChatMessage(errorMsg);
        setStreaming(false);
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
      enterChatMode,
      addChatMessage,
      setStreaming,
      sendChatMessage,
    ]
  );

  // Plan 승인
  const approvePlan = useCallback(
    async (messageId: string) => {
      // plan 메시지를 승인 상태로 업데이트
      updateChatMessage(messageId, { approved: true });

      // 승인 메시지 추가
      const userMsg: ChatMessage = {
        id: `chat-${Date.now()}-approve`,
        role: 'user',
        content: '승인합니다',
        timestamp: new Date(),
      };
      addChatMessage(userMsg);

      // 승인 결과 응답 요청
      try {
        const response = await agentService.processChatMessage('승인합니다');
        const agentMsg: ChatMessage = {
          id: `chat-${Date.now()}-approve-result`,
          role: 'agent',
          type: response.type,
          content: response.message,
          timestamp: new Date(),
        };
        setStreaming(true);
        addChatMessage(agentMsg);
        // 응답 완료 후 스트리밍 종료
        setStreaming(false);
      } catch {
        const errorMsg: ChatMessage = {
          id: `chat-${Date.now()}-approve-error`,
          role: 'agent',
          content: '승인 처리 중 오류가 발생했습니다.',
          timestamp: new Date(),
        };
        setStreaming(true);
        addChatMessage(errorMsg);
        setStreaming(false);
      }
    },
    [updateChatMessage, addChatMessage, setStreaming]
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
