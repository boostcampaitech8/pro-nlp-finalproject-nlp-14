// Spotlight 입력창 컴포넌트
import { useRef, useEffect } from 'react';
import { Loader2, Send } from 'lucide-react';
import { useCommand } from '@/app/hooks/useCommand';
import { useCommandStore } from '@/app/stores/commandStore';
import { cn } from '@/lib/utils';

export function SpotlightInput() {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { inputValue, setInputValue, submitCommand, isChatMode, cancelPendingMessage } = useCommand();
  const { isProcessing, isInputFocused, setInputFocused, isStreaming, pendingMessages } = useCommandStore();

  // Cmd+K 단축키 처리
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 채팅 모드 진입 시 자동 포커스
  useEffect(() => {
    if (isChatMode) {
      inputRef.current?.focus();
    }
  }, [isChatMode]);

  // 답변 완료 후 (isStreaming false) 포커스 유지
  useEffect(() => {
    if (isChatMode && !isStreaming && !isProcessing) {
      inputRef.current?.focus();
    }
  }, [isChatMode, isStreaming, isProcessing]);

  const isSendDisabled = pendingMessages.length > 0 || !inputValue.trim();

  const resizeTextarea = () => {
    const node = inputRef.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${node.scrollHeight}px`;
  };

  useEffect(() => {
    resizeTextarea();
  }, [inputValue]);

  const handleSubmit = () => {
    if (isSendDisabled) return;
    submitCommand();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 한글 입력 중(IME composing) Enter 무시 - 두 번 입력 버그 방지
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;

    if (e.key === 'ArrowUp' && pendingMessages.length > 0) {
      const { selectionStart, selectionEnd, value } = e.currentTarget;
      if (selectionStart !== null && selectionStart === selectionEnd) {
        const beforeCursor = value.slice(0, selectionStart);
        if (!beforeCursor.includes('\n')) {
          const pending = pendingMessages[0];
          e.preventDefault();
          setInputValue(pending.text);
          cancelPendingMessage(pending.id);
          requestAnimationFrame(() => {
            const node = inputRef.current;
            if (!node) return;
            const end = node.value.length;
            node.setSelectionRange(end, end);
          });
          return;
        }
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      className={cn(
        'glass-input flex items-center gap-4 px-5 py-4 transition-all duration-200',
        isInputFocused && 'border-mit-primary/50 shadow-input-focus'
      )}
    >
      <span className="text-white/30 text-sm flex-shrink-0">
        {isProcessing ? (
          <Loader2 className="w-5 h-5 text-white animate-spin" aria-hidden="true" />
        ) : (
          '>'
        )}
      </span>

      {/* 입력 필드 */}
      <textarea
        ref={inputRef}
        rows={1}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setInputFocused(true)}
        onBlur={() => setInputFocused(false)}
        placeholder={isChatMode ? '이어서 질문해보세요...' : '회의를 시작하거나, 무엇이든 물어보세요...'}
        aria-label="Mit에게 메시지 입력"
        className="flex-1 bg-transparent text-[15px] text-white placeholder:text-white/40 outline-none resize-none min-h-[24px] max-h-[150px] leading-6 overflow-y-auto scrollbar-hide"
      />

      {/* 단축키 힌트 */}
      {!isChatMode && !isInputFocused && !inputValue && (
        <div className="flex items-center gap-1 flex-shrink-0">
          <span className="shortcut-key">Cmd</span>
          <span className="shortcut-key">K</span>
        </div>
      )}

      {isChatMode && (
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSendDisabled}
          className={cn(
            'flex-shrink-0 p-1.5 rounded-full transition-colors',
            isSendDisabled ? 'text-white/25 cursor-not-allowed' : 'text-white/70 hover:text-white'
          )}
          title="보내기 (Enter)"
          aria-label="메시지 보내기"
        >
          <Send className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
