/**
 * 채팅 패널 컴포넌트
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage } from '@/types/chat';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (content: string) => void;
  disabled?: boolean;
  currentUserId?: string;
  hideHeader?: boolean;
}

export function ChatPanel({
  messages,
  onSendMessage,
  disabled = false,
  currentUserId,
  hideHeader = false,
}: ChatPanelProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 새 메시지가 오면 스크롤
  useEffect(() => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();

      const trimmedValue = inputValue.trim();
      if (!trimmedValue) return;

      onSendMessage(trimmedValue);
      setInputValue('');
    },
    [inputValue, onSendMessage]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // 한글 IME 조합 중에는 Enter 처리하지 않음
      if (e.nativeEvent.isComposing) return;

      // Enter만 누르면 전송, Shift+Enter는 줄바꿈
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const trimmedValue = inputValue.trim();
        if (!trimmedValue) return;

        onSendMessage(trimmedValue);
        setInputValue('');
      }
    },
    [inputValue, onSendMessage]
  );

  // 시간 포맷
  const formatTime = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  // 연속 메시지 여부 확인 (같은 사람이 1분 이내에 보낸 메시지)
  const isContinuousMessage = (index: number): boolean => {
    if (index === 0) return false;

    const currentMsg = messages[index];
    const prevMsg = messages[index - 1];

    // 같은 사람이 아니면 false
    if (currentMsg.userId !== prevMsg.userId) return false;

    // 시간 차이 계산 (1분 = 60000ms)
    try {
      const currentTime = new Date(currentMsg.createdAt).getTime();
      const prevTime = new Date(prevMsg.createdAt).getTime();
      return currentTime - prevTime < 60000;
    } catch {
      return false;
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-800 rounded-lg">
      {/* 헤더 */}
      {!hideHeader && (
        <div className="px-4 py-3 border-b border-gray-700">
          <h3 className="text-white font-medium">채팅</h3>
        </div>
      )}

      {/* 메시지 목록 */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            메시지가 없습니다
          </div>
        ) : (
          messages.map((message, index) => {
            const isOwn = currentUserId === message.userId;
            const isContinuous = isContinuousMessage(index);
            return (
              <div
                key={message.id}
                className={`flex flex-col ${isOwn ? 'items-end' : 'items-start'} ${isContinuous ? 'mt-0.5' : ''}`}
              >
                {!isContinuous && (
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-400">{message.userName}</span>
                    <span className="text-xs text-gray-500">{formatTime(message.createdAt)}</span>
                  </div>
                )}
                <div
                  className={`px-3 py-2 rounded-lg max-w-[85%] break-words ${
                    isOwn
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-100'
                  }`}
                >
                  <MarkdownRenderer
                    content={message.content}
                    className={`prose-p:my-0 prose-headings:my-1 ${isOwn ? 'prose-invert' : 'prose-invert'}`}
                  />
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 입력 영역 */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-gray-700">
        <div className="flex gap-2 items-end">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="메시지를 입력하세요... (Shift+Enter: 줄바꿈)"
            disabled={disabled}
            rows={1}
            className="flex-1 px-3 py-2 bg-gray-700 text-white rounded-lg placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed resize-none min-h-[40px] max-h-[120px] overflow-y-auto"
            style={{ height: 'auto' }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = 'auto';
              target.style.height = Math.min(target.scrollHeight, 120) + 'px';
            }}
          />
          <button
            type="submit"
            disabled={disabled}
            aria-label="보내기"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}
