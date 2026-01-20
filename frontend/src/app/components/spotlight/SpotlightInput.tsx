// Spotlight 입력창 컴포넌트
import { useRef, useEffect } from 'react';
import { Command, Mic, Settings, Loader2, MessageCircle } from 'lucide-react';
import { useCommand } from '@/app/hooks/useCommand';
import { useCommandStore } from '@/app/stores/commandStore';
import { useConversationStore } from '@/app/stores/conversationStore';
import { cn } from '@/lib/utils';

export function SpotlightInput() {
  const inputRef = useRef<HTMLInputElement>(null);
  const { inputValue, setInputValue, submitCommand } = useCommand();
  const { isProcessing, isInputFocused, setInputFocused } = useCommandStore();
  const { startConversation, addMessage } = useConversationStore();

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

  // 대화 모드로 전환하며 명령 실행
  const handleSubmitWithConversation = () => {
    if (!inputValue.trim() || isProcessing) return;

    // 대화 모드 시작
    startConversation();

    // 사용자 메시지 추가
    addMessage({ type: 'user', content: inputValue.trim() });

    // 로딩 메시지 추가
    addMessage({
      type: 'agent',
      content: '',
      agentData: { responseType: 'loading' },
    });

    // 기존 명령 실행 (결과는 대화에 반영됨)
    submitCommand();
  };

  const handleSubmit = () => {
    if (!inputValue.trim() || isProcessing) return;
    handleSubmitWithConversation();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // 대화 모드로 전환만 (입력 없이)
  const handleStartConversation = () => {
    startConversation();
    addMessage({
      type: 'system',
      content: '대화를 시작합니다. 무엇이든 물어보세요.',
    });
  };

  return (
    <div
      className={cn(
        'glass-input flex items-center gap-4 px-5 py-4 transition-all duration-200',
        isInputFocused && 'border-mit-primary/50 shadow-input-focus'
      )}
    >
      {/* 아이콘 */}
      <div className="icon-container flex-shrink-0">
        {isProcessing ? (
          <Loader2 className="w-5 h-5 text-white animate-spin" />
        ) : (
          <Command className="w-5 h-5 text-white" />
        )}
      </div>

      {/* 입력 필드 */}
      <input
        ref={inputRef}
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setInputFocused(true)}
        onBlur={() => setInputFocused(false)}
        placeholder="Mit에게 무엇이든 물어보세요..."
        disabled={isProcessing}
        className="flex-1 bg-transparent text-[15px] text-white placeholder:text-white/40 outline-none disabled:opacity-50"
      />

      {/* 액션 버튼 */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          className="action-btn"
          title="음성 입력"
          disabled={isProcessing}
        >
          <Mic className="w-4 h-4 text-white/60" />
        </button>
        <button
          className="action-btn"
          title="대화 모드"
          onClick={handleStartConversation}
        >
          <MessageCircle className="w-4 h-4 text-white/60" />
        </button>
        <button
          className="action-btn"
          title="설정"
        >
          <Settings className="w-4 h-4 text-white/60" />
        </button>

        {/* 단축키 힌트 */}
        {!isInputFocused && !inputValue && (
          <div className="flex gap-1 ml-2">
            <span className="shortcut-key">Cmd</span>
            <span className="shortcut-key">K</span>
          </div>
        )}
      </div>
    </div>
  );
}
