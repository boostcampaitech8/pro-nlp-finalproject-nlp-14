/**
 * 시그널링 훅
 * WebSocket 연결 및 시그널링 메시지 처리 담당
 */

import { useCallback, useRef } from 'react';
import { signalingClient } from '@/services/signalingService';
import type { ClientMessage, ServerMessage } from '@/types/webrtc';

interface UseSignalingOptions {
  meetingId: string;
  onMessage: (message: ServerMessage) => void;
  onError?: (error: string) => void;
}

interface UseSignalingReturn {
  connect: (token: string) => Promise<void>;
  disconnect: () => void;
  send: (message: ClientMessage) => void;
  isConnected: boolean;
}

export function useSignaling({
  meetingId,
  onMessage,
  onError,
}: UseSignalingOptions): UseSignalingReturn {
  const isConnectedRef = useRef(false);

  /**
   * 시그널링 서버 연결
   */
  const connect = useCallback(
    async (token: string) => {
      try {
        // 메시지 핸들러 등록
        signalingClient.onMessage(onMessage);

        // WebSocket 연결
        await signalingClient.connect(meetingId, token);
        isConnectedRef.current = true;
      } catch (err) {
        console.error('[useSignaling] Connection failed:', err);
        isConnectedRef.current = false;
        if (onError) {
          onError(err instanceof Error ? err.message : '시그널링 서버 연결 실패');
        }
        throw err;
      }
    },
    [meetingId, onMessage, onError]
  );

  /**
   * 시그널링 서버 연결 해제
   */
  const disconnect = useCallback(() => {
    if (signalingClient.isConnected) {
      signalingClient.send({ type: 'leave' });
    }
    signalingClient.disconnect();
    isConnectedRef.current = false;
  }, []);

  /**
   * 메시지 전송
   */
  const send = useCallback((message: ClientMessage) => {
    if (signalingClient.isConnected) {
      signalingClient.send(message);
    } else {
      console.warn('[useSignaling] Cannot send message: not connected');
    }
  }, []);

  return {
    connect,
    disconnect,
    send,
    isConnected: signalingClient.isConnected,
  };
}
