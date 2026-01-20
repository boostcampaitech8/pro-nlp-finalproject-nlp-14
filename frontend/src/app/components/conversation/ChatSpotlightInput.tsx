// 하단 고정 채팅 입력창 컴포넌트
import { useRef, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Send, Loader2, X, Settings, Maximize2, Minimize2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useConversationStore } from '@/app/stores/conversationStore';
import type { LayoutMode } from '@/app/types/conversation';

interface ChatSpotlightInputProps {
  onSubmit: (command: string) => void;
  isProcessing?: boolean;
  placeholder?: string;
}

// 레이아웃 모드 아이콘 매핑
const layoutIcons: Record<LayoutMode, React.ReactNode> = {
  'center-only': <Minimize2 className="w-4 h-4" />,
  fullscreen: <Maximize2 className="w-4 h-4" />,
  'center-right-merged': <Settings className="w-4 h-4" />,
};

export function ChatSpotlightInput({
  onSubmit,
  isProcessing = false,
  placeholder = '메시지를 입력하세요...',
}: ChatSpotlightInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const { endConversation, layoutMode, setLayoutMode } = useConversationStore();

  // 자동 포커스
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = () => {
    if (!value.trim() || isProcessing) return;
    onSubmit(value.trim());
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    // ESC로 대화 종료
    if (e.key === 'Escape') {
      endConversation();
    }
  };

  // 레이아웃 모드 순환
  const cycleLayoutMode = () => {
    const modes: LayoutMode[] = ['center-only', 'fullscreen', 'center-right-merged'];
    const currentIndex = modes.indexOf(layoutMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    setLayoutMode(modes[nextIndex]);
  };

  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.3, delay: 0.1 }}
      className="p-4 border-t border-white/10"
    >
      <div
        className={cn(
          'glass-input flex items-center gap-3 px-4 py-3 transition-all duration-200',
          isFocused && 'border-mit-primary/50 shadow-input-focus'
        )}
      >
        {/* 대화 종료 버튼 */}
        <button
          onClick={endConversation}
          className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          title="대화 종료 (ESC)"
        >
          <X className="w-4 h-4 text-white/60" />
        </button>

        {/* 입력 필드 */}
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          disabled={isProcessing}
          className="flex-1 bg-transparent text-[15px] text-white placeholder:text-white/40 outline-none disabled:opacity-50"
        />

        {/* 레이아웃 모드 버튼 */}
        <button
          onClick={cycleLayoutMode}
          className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          title={`레이아웃: ${layoutMode}`}
        >
          {layoutIcons[layoutMode]}
          <span className="sr-only">{layoutMode}</span>
        </button>

        {/* 전송 버튼 */}
        <button
          onClick={handleSubmit}
          disabled={!value.trim() || isProcessing}
          className={cn(
            'p-2 rounded-lg transition-all duration-200',
            value.trim() && !isProcessing
              ? 'bg-mit-primary hover:bg-mit-primary/80 text-white'
              : 'bg-white/5 text-white/30'
          )}
        >
          {isProcessing ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* 힌트 */}
      <div className="flex justify-center mt-2">
        <span className="text-[11px] text-white/30">
          Enter로 전송 | ESC로 종료
        </span>
      </div>
    </motion.div>
  );
}
