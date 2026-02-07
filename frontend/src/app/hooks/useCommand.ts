// 명령 처리 훅
import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCommandStore } from '@/app/stores/commandStore';
import { spotlightApi, type SSEEvent, type SpotlightSession } from '@/app/services/spotlightApi';
import type { ChatMessage, HITLData } from '@/app/types/command';

type QueueItem =
  | { kind: 'message'; text: string; sessionId: string }
  | { kind: 'hitl'; action: 'confirm' | 'cancel'; params?: Record<string, unknown>; sessionId: string };

const requestQueue: QueueItem[] = [];
let queueProcessing = false;
let hitlPending = false;
let queueSessionId: string | null = null;

const resetQueueState = () => {
  requestQueue.length = 0;
  queueProcessing = false;
  hitlPending = false;
  queueSessionId = null;
};

export function useCommand() {
  const navigate = useNavigate();
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
    autoCancelPendingHitl,
    setStreaming,
    setStatusMessage,
    createNewSession,
    setAbortController,
    abortCurrentStream,
    syncSessionMessages,
    markSessionNewResponse,
    updateSessionTitle,
  } = useCommandStore();

  // 현재 세션 ID를 ref로 추적 (콜백에서 최신 값 참조용)
  const currentSessionIdRef = useRef(currentSessionId);
  currentSessionIdRef.current = currentSessionId;
  const sessionCreationRef = useRef<Promise<SpotlightSession | null> | null>(null);

  useEffect(() => {
    if (!currentSessionId) {
      resetQueueState();
      return;
    }
    if (queueSessionId && queueSessionId !== currentSessionId) {
      resetQueueState();
    }
    queueSessionId = currentSessionId;
  }, [currentSessionId]);

  const processQueue = useCallback(() => {
    if (queueProcessing) return;
    if (requestQueue.length === 0) return;

    let nextIndex = 0;
    if (hitlPending) {
      nextIndex = requestQueue.findIndex((item) => item.kind === 'hitl');
      if (nextIndex === -1) return;
    }

    const [nextItem] = requestQueue.splice(nextIndex, 1);
    if (!nextItem) return;

    queueProcessing = true;

    const completeItem = (options?: { setHitlPending?: boolean }) => {
      if (typeof options?.setHitlPending === 'boolean') {
        hitlPending = options.setHitlPending;
      }
      queueProcessing = false;
      processQueue();
    };

    if (nextItem.kind === 'message') {
      startMessageStream(nextItem, completeItem);
    } else {
      startHitlStream(nextItem, completeItem);
    }
  }, []);

  const enqueueMessage = useCallback(
    (text: string, sessionId: string) => {
      requestQueue.push({ kind: 'message', text, sessionId });
      processQueue();
    },
    [processQueue]
  );

  const enqueueHitl = useCallback(
    (action: 'confirm' | 'cancel', sessionId: string, params?: Record<string, unknown>) => {
      requestQueue.unshift({ kind: 'hitl', action, params, sessionId });
      processQueue();
    },
    [processQueue]
  );

  const ensureSessionId = useCallback(async () => {
    if (currentSessionIdRef.current) return currentSessionIdRef.current;

    if (!sessionCreationRef.current) {
      setProcessing(true);
      enterChatMode();
      sessionCreationRef.current = createNewSession();
    }

    const session = await sessionCreationRef.current;
    sessionCreationRef.current = null;
    setProcessing(false);

    // 세션 생성 후 ref 즉시 동기 업데이트
    // React 리렌더(macrotask)보다 먼저 실행되는 microtask 체인에서
    // SSE 콜백이 올바른 sessionId를 참조할 수 있도록 보장
    if (session?.id) {
      currentSessionIdRef.current = session.id;
    }

    return session?.id ?? null;
  }, [createNewSession, setProcessing, enterChatMode]);

  const startMessageStream = useCallback(
    async (
      item: QueueItem & { kind: 'message' },
      completeItem: (options?: { setHitlPending?: boolean }) => void
    ) => {
      const streamSessionId = item.sessionId;
      let completed = false;
      const finish = (options?: { setHitlPending?: boolean }) => {
        if (completed) return;
        completed = true;
        completeItem(options);
      };

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

      try {
        abortCurrentStream();

        const controller = await spotlightApi.chatStream(
          streamSessionId,
          item.text,
          (event: SSEEvent) => {
            const isCurrentSession = useCommandStore.getState().currentSessionId === streamSessionId;

            if (event.type === 'message' && event.data) {
              if (!isCurrentSession) return;
              setStatusMessage(null);
              updateChatMessage(agentMsgId, {
                content: (prev: string) => prev + event.data,
              });
            } else if (event.type === 'status' && event.data) {
              if (!isCurrentSession) return;
              setStatusMessage(event.data);
            } else if (event.type === 'done') {
              if (isCurrentSession) {
                setStatusMessage(null);
                setStreaming(false);
                setAbortController(null);
              } else {
                markSessionNewResponse(streamSessionId);
              }
              finish();
            } else if (event.type === 'error') {
              if (isCurrentSession) {
                setStatusMessage(null);
                if (event.error !== '세션이 만료되었습니다.' && streamSessionId) {
                  setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
                  setTimeout(async () => {
                    await syncSessionMessages(streamSessionId);
                    setStatusMessage(null);
                  }, 2000);
                } else {
                  updateChatMessage(agentMsgId, {
                    content: event.error || '응답 처리 중 오류가 발생했습니다.',
                  });
                }

                setStreaming(false);
                setAbortController(null);
              }
              finish();
            } else if (event.type === 'hitl_request') {
              if (isCurrentSession) {
                setStatusMessage(null);
                setStreaming(false);
                setAbortController(null);

                const hitlData: HITLData = {
                  tool_name: event.tool_name || '',
                  params: event.params || {},
                  params_display: event.params_display || {},
                  message: event.message || '',
                  required_fields: event.required_fields || [],
                  display_template: event.display_template,
                };

                const hitlMsg: ChatMessage = {
                  id: `hitl-${Date.now()}`,
                  role: 'agent',
                  type: 'hitl',
                  content: event.message || '작업을 수행할까요?',
                  timestamp: new Date(),
                  hitlData,
                  hitlStatus: 'pending',
                };
                addChatMessage(hitlMsg);
                finish({ setHitlPending: true });
              } else {
                finish();
              }
            }
          }
        );

        setAbortController(controller);
      } catch (error) {
        if ((error as Error).name === 'AbortError') {
          finish();
          return;
        }

        setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
        setStreaming(false);
        setAbortController(null);

        setTimeout(async () => {
          await syncSessionMessages(streamSessionId);
          setStatusMessage(null);
        }, 3000);

        finish();
      }
    },
    [addChatMessage, updateChatMessage, setStreaming, setStatusMessage, setAbortController, abortCurrentStream, syncSessionMessages, markSessionNewResponse]
  );

  const startHitlStream = useCallback(
    async (
      item: QueueItem & { kind: 'hitl' },
      completeItem: (options?: { setHitlPending?: boolean }) => void
    ) => {
      const streamSessionId = item.sessionId;
      let completed = false;
      const finish = (options?: { setHitlPending?: boolean }) => {
        if (completed) return;
        completed = true;
        completeItem(options);
      };

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

      try {
        abortCurrentStream();

        const controller = await spotlightApi.chatStream(
          streamSessionId,
          '',
          (event: SSEEvent) => {
            const isCurrentSession = useCommandStore.getState().currentSessionId === streamSessionId;

            if (event.type === 'message' && event.data) {
              if (!isCurrentSession) return;
              setStatusMessage(null);
              updateChatMessage(agentMsgId, {
                content: (prev: string) => prev + event.data,
              });
            } else if (event.type === 'status' && event.data) {
              if (!isCurrentSession) return;
              setStatusMessage(event.data);
            } else if (event.type === 'done') {
              if (isCurrentSession) {
                setStatusMessage(null);
                setStreaming(false);
                setAbortController(null);
              } else {
                markSessionNewResponse(streamSessionId);
              }
              finish(isCurrentSession ? { setHitlPending: false } : undefined);
            } else if (event.type === 'error') {
              if (isCurrentSession) {
                setStatusMessage(null);
                if (event.error !== '세션이 만료되었습니다.' && streamSessionId) {
                  setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
                  setTimeout(async () => {
                    await syncSessionMessages(streamSessionId);
                    setStatusMessage(null);
                  }, 2000);
                } else {
                  updateChatMessage(agentMsgId, {
                    content: event.error || '작업 처리 중 오류가 발생했습니다.',
                  });
                }

                setStreaming(false);
                setAbortController(null);
                finish({ setHitlPending: true });
              } else {
                finish();
              }
            } else if (event.type === 'hitl_request') {
              if (isCurrentSession) {
                setStatusMessage(null);
                setStreaming(false);
                setAbortController(null);

                const hitlData: HITLData = {
                  tool_name: event.tool_name || '',
                  params: event.params || {},
                  params_display: event.params_display || {},
                  message: event.message || '',
                  required_fields: event.required_fields || [],
                  display_template: event.display_template,
                };

                const hitlMsg: ChatMessage = {
                  id: `hitl-${Date.now()}`,
                  role: 'agent',
                  type: 'hitl',
                  content: event.message || '작업을 수행할까요?',
                  timestamp: new Date(),
                  hitlData,
                  hitlStatus: 'pending',
                };
                addChatMessage(hitlMsg);
                finish({ setHitlPending: true });
              } else {
                finish();
              }
            }
          },
          item.action,
          item.params
        );

        setAbortController(controller);
      } catch (error) {
        if ((error as Error).name === 'AbortError') {
          finish();
          return;
        }

        setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
        setStreaming(false);
        setAbortController(null);

        setTimeout(async () => {
          await syncSessionMessages(streamSessionId);
          setStatusMessage(null);
        }, 3000);

        finish({ setHitlPending: true });
      }
    },
    [addChatMessage, updateChatMessage, setStreaming, setStatusMessage, setAbortController, abortCurrentStream, syncSessionMessages, markSessionNewResponse]
  );

  // 명령 제출 (항상 Spotlight API 사용)
  const submitCommand = useCallback(
    async (command?: string) => {
      const cmd = command || inputValue;
      if (!cmd.trim()) return;

      setInputValue('');

      const wasInChatMode = isChatMode;

      if (!isChatMode) {
        enterChatMode();
      }

      const sessionId = await ensureSessionId();
      if (!sessionId) return;

      // 새 세션이 생성된 경우 URL 업데이트
      if (!wasInChatMode) {
        navigate(`/spotlight/${sessionId}`, { replace: true });
      }

      // HITL pending 상태면 자동 취소 표시 후 새 메시지 전송
      if (hitlPending) {
        autoCancelPendingHitl();
        hitlPending = false;
      }

      const userMsg: ChatMessage = {
        id: `chat-${Date.now()}-user`,
        role: 'user',
        type: 'text',
        content: cmd,
        timestamp: new Date(),
      };
      addChatMessage(userMsg);

      // 첫 메시지인 경우 세션 제목을 유저 메시지로 설정
      if (!wasInChatMode) {
        const title = cmd.length > 50 ? cmd.slice(0, 50) + '...' : cmd;
        updateSessionTitle(sessionId, title);
      }

      enqueueMessage(cmd, sessionId);
    },
    [
      inputValue,
      isChatMode,
      navigate,
      setInputValue,
      enterChatMode,
      ensureSessionId,
      addChatMessage,
      enqueueMessage,
      autoCancelPendingHitl,
      updateSessionTitle,
    ]
  );

  // Plan 승인 (Spotlight API로 전송)
  const approvePlan = useCallback(
    async (messageId: string) => {
      // plan 메시지를 승인 상태로 업데이트
      updateChatMessage(messageId, { approved: true });

      const sessionId = await ensureSessionId();
      if (!sessionId) return;

      const userMsg: ChatMessage = {
        id: `chat-${Date.now()}-user`,
        role: 'user',
        type: 'text',
        content: '승인합니다',
        timestamp: new Date(),
      };
      addChatMessage(userMsg);
      enqueueMessage('승인합니다', sessionId);
    },
    [updateChatMessage, ensureSessionId, addChatMessage, enqueueMessage]
  );

  // HITL 확인 (Confirm)
  const confirmHITL = useCallback(
    async (messageId: string, params?: Record<string, unknown>) => {
      // 세션 확인
      const sessionId = currentSessionIdRef.current;
      if (!sessionId) return;

      // HITL 메시지 상태 업데이트
      updateChatMessage(messageId, { hitlStatus: 'confirmed' });

      enqueueHitl('confirm', sessionId, params);
    },
    [updateChatMessage, enqueueHitl]
  );

  // HITL 취소 (Cancel)
  const cancelHITL = useCallback(
    async (messageId: string) => {
      // 세션 확인
      const sessionId = currentSessionIdRef.current;
      if (!sessionId) return;

      // HITL 메시지 상태 업데이트
      updateChatMessage(messageId, { hitlStatus: 'cancelled', hitlCancelReason: 'user' });

      enqueueHitl('cancel', sessionId);
    },
    [updateChatMessage, enqueueHitl]
  );

  const handleExitChatMode = useCallback(() => {
    exitChatMode();
    navigate('/', { replace: true });
  }, [exitChatMode, navigate]);

  return {
    inputValue,
    isChatMode,
    setInputValue,
    submitCommand,
    approvePlan,
    confirmHITL,
    cancelHITL,
    exitChatMode: handleExitChatMode,
  };
}
