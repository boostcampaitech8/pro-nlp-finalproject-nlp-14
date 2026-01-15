// Spotlight 입력창 컴포넌트
import { useRef, useEffect } from 'react';
import { Command, Mic, Settings, Loader2 } from 'lucide-react';
import { useCommand } from '@/app/hooks/useCommand';
import { useCommandStore } from '@/app/stores/commandStore';
import { cn } from '@/lib/utils';

export function SpotlightInput() {
  const inputRef = useRef<HTMLInputElement>(null);
  const { inputValue, setInputValue, submitCommand } = useCommand();
  const { isProcessing, isInputFocused, setInputFocused } = useCommandStore();

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

  const handleSubmit = () => {
    if (!inputValue.trim() || isProcessing) return;
    submitCommand();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
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
