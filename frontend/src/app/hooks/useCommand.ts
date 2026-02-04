// 명령 처리 훅
import { useCallback, useRef } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { spotlightApi, type SSEEvent } from '@/app/services/spotlightApi';
import type { ChatMessage, HITLData } from '@/app/types/command';

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
    setAbortController,
    abortCurrentStream,
    syncSessionMessages,
    markSessionNewResponse,
  } = useCommandStore();

  // 현재 세션 ID를 ref로 추적 (콜백에서 최신 값 참조용)
  const currentSessionIdRef = useRef(currentSessionId);
  currentSessionIdRef.current = currentSessionId;

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
        // ref도 즉시 업데이트하여 race condition 방지
        currentSessionIdRef.current = sessionId;
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

      // SSE 스트림 시작 (세션 ID 캡처하여 이벤트 격리)
      const streamSessionId = sessionId;
      try {
        // 기존 스트림 정리
        abortCurrentStream();

        const controller = await spotlightApi.chatStream(
          sessionId,
          text,
          (event: SSEEvent) => {
            // 세션 ID가 변경되었으면 이벤트 무시 (세션 전환 시 격리)
            if (currentSessionIdRef.current !== streamSessionId) {
              console.log('[SSE] Ignoring event from different session:', streamSessionId);
              return;
            }

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
              setAbortController(null); // 스트림 완료 시 컨트롤러 정리
              // 현재 보고 있는 세션이 아니면 새 응답 표시 (세션 전환 후 완료된 경우)
              if (currentSessionIdRef.current !== streamSessionId) {
                markSessionNewResponse(streamSessionId);
              }
            } else if (event.type === 'error') {
              setStatusMessage(null);

              // 세션 만료 에러가 아닌 경우 자동 동기화 시도
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
            } else if (event.type === 'hitl_request') {
              // HITL 확인 요청 - 별도 메시지로 추가
              setStatusMessage(null);
              setStreaming(false);
              setAbortController(null);

              const hitlData: HITLData = {
                tool_name: event.tool_name || '',
                params: event.params || {},
                params_display: event.params_display || {}, // UUID → 이름 변환된 표시용 값
                message: event.message || '',
                required_fields: event.required_fields || [],
                display_template: event.display_template, // 자연어 템플릿
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
            }
          }
        );

        // AbortController 저장 (세션 전환 시 취소용)
        setAbortController(controller);
      } catch (error) {
        // AbortError는 정상적인 취소이므로 무시
        if ((error as Error).name === 'AbortError') {
          console.log('[SSE] Stream aborted (session switch or cleanup)');
          return;
        }

        // 네트워크 에러 시 자동 동기화 시도
        setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
        setStreaming(false);
        setAbortController(null);

        // 3초 후 서버에서 최신 메시지 동기화
        if (sessionId) {
          setTimeout(async () => {
            await syncSessionMessages(sessionId);
            setStatusMessage(null);
          }, 3000);
        } else {
          updateChatMessage(agentMsgId, {
            content: '응답 처리 중 오류가 발생했습니다. 다시 시도해주세요.',
          });
          setStatusMessage(null);
        }
      }
    },
    [currentSessionId, createNewSession, addChatMessage, updateChatMessage, setStreaming, setStatusMessage, setAbortController, abortCurrentStream, syncSessionMessages, markSessionNewResponse]
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

  // HITL 확인 (Confirm)
  const confirmHITL = useCallback(
    async (messageId: string, params?: Record<string, unknown>) => {
      // 세션 확인
      if (!currentSessionId) return;

      // HITL 메시지 상태 업데이트
      updateChatMessage(messageId, { hitlStatus: 'confirmed' });

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

      // HITL confirm 액션과 함께 API 호출 (사용자 입력 파라미터 포함)
      const streamSessionId = currentSessionId;
      try {
        // 기존 스트림 정리
        abortCurrentStream();

        const controller = await spotlightApi.chatStream(
          currentSessionId,
          '', // 빈 메시지 (HITL 응답이므로)
          (event: SSEEvent) => {
            // 세션 ID가 변경되었으면 이벤트 무시
            if (currentSessionIdRef.current !== streamSessionId) {
              return;
            }

            if (event.type === 'message' && event.data) {
              setStatusMessage(null);
              updateChatMessage(agentMsgId, {
                content: (prev: string) => prev + event.data,
              });
            } else if (event.type === 'status' && event.data) {
              setStatusMessage(event.data);
            } else if (event.type === 'done') {
              setStatusMessage(null);
              setStreaming(false);
              setAbortController(null);
              // 현재 보고 있는 세션이 아니면 새 응답 표시
              if (currentSessionIdRef.current !== streamSessionId) {
                markSessionNewResponse(streamSessionId);
              }
            } else if (event.type === 'error') {
              setStatusMessage(null);

              // 세션 만료 에러가 아닌 경우 자동 동기화 시도
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
            }
          },
          'confirm',
          params, // 사용자 입력 파라미터 전달
        );

        setAbortController(controller);
      } catch (error) {
        if ((error as Error).name === 'AbortError') return;

        // 네트워크 에러 시 자동 동기화 시도
        setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
        setStreaming(false);
        setAbortController(null);

        if (currentSessionId) {
          setTimeout(async () => {
            await syncSessionMessages(currentSessionId);
            setStatusMessage(null);
          }, 3000);
        } else {
          updateChatMessage(agentMsgId, {
            content: '작업 처리 중 오류가 발생했습니다.',
          });
          setStatusMessage(null);
        }
      }
    },
    [currentSessionId, addChatMessage, updateChatMessage, setStreaming, setStatusMessage, setAbortController, abortCurrentStream, syncSessionMessages, markSessionNewResponse]
  );

  // HITL 취소 (Cancel)
  const cancelHITL = useCallback(
    async (messageId: string) => {
      // 세션 확인
      if (!currentSessionId) return;

      // HITL 메시지 상태 업데이트
      updateChatMessage(messageId, { hitlStatus: 'cancelled' });

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

      // HITL cancel 액션과 함께 API 호출
      const streamSessionId = currentSessionId;
      try {
        // 기존 스트림 정리
        abortCurrentStream();

        const controller = await spotlightApi.chatStream(
          currentSessionId,
          '',
          (event: SSEEvent) => {
            // 세션 ID가 변경되었으면 이벤트 무시
            if (currentSessionIdRef.current !== streamSessionId) {
              return;
            }

            if (event.type === 'message' && event.data) {
              setStatusMessage(null);
              updateChatMessage(agentMsgId, {
                content: (prev: string) => prev + event.data,
              });
            } else if (event.type === 'status' && event.data) {
              setStatusMessage(event.data);
            } else if (event.type === 'done') {
              setStatusMessage(null);
              setStreaming(false);
              setAbortController(null);
              // 현재 보고 있는 세션이 아니면 새 응답 표시
              if (currentSessionIdRef.current !== streamSessionId) {
                markSessionNewResponse(streamSessionId);
              }
            } else if (event.type === 'error') {
              setStatusMessage(null);

              // 세션 만료 에러가 아닌 경우 자동 동기화 시도
              if (event.error !== '세션이 만료되었습니다.' && streamSessionId) {
                setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
                setTimeout(async () => {
                  await syncSessionMessages(streamSessionId);
                  setStatusMessage(null);
                }, 2000);
              } else {
                updateChatMessage(agentMsgId, {
                  content: event.error || '취소 처리 중 오류가 발생했습니다.',
                });
              }

              setStreaming(false);
              setAbortController(null);
            }
          },
          'cancel'
        );

        setAbortController(controller);
      } catch (error) {
        if ((error as Error).name === 'AbortError') return;

        // 네트워크 에러 시 자동 동기화 시도
        setStatusMessage('연결이 끊어졌습니다. 결과를 확인하는 중...');
        setStreaming(false);
        setAbortController(null);

        if (currentSessionId) {
          setTimeout(async () => {
            await syncSessionMessages(currentSessionId);
            setStatusMessage(null);
          }, 3000);
        } else {
          updateChatMessage(agentMsgId, {
            content: '취소 처리 중 오류가 발생했습니다.',
          });
          setStatusMessage(null);
        }
      }
    },
    [currentSessionId, addChatMessage, updateChatMessage, setStreaming, setStatusMessage, setAbortController, abortCurrentStream, syncSessionMessages, markSessionNewResponse]
  );

  return {
    inputValue,
    isChatMode,
    setInputValue,
    submitCommand,
    approvePlan,
    confirmHITL,
    cancelHITL,
    exitChatMode,
  };
}
