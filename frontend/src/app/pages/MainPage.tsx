// 새 서비스 메인 페이지 (Spotlight UI)
import { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useCommandStore } from '@/app/stores/commandStore';
import { agentService } from '@/app/services/agentService';
import {
  SpotlightInput,
  CommandSuggestions,
  CommandHistory,
  InteractiveForm,
  ChatFlow,
} from '@/app/components/spotlight';
import { ScrollArea } from '@/app/components/ui';

const layoutTransition = {
  duration: 0.4,
  ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
};

export function MainPage() {
  const { activeCommand, isChatMode, setSuggestions } = useCommandStore();
  const exitChatMode = useCommandStore((s) => s.exitChatMode);

  // 추천 명령어 로드
  useEffect(() => {
    agentService.getSuggestions().then(setSuggestions);
  }, [setSuggestions]);

  // ESC 키로 채팅 모드 종료
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isChatMode) {
        exitChatMode();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isChatMode, exitChatMode]);

  // 채팅 모드
  if (isChatMode) {
    return (
      <motion.div
        className="flex-1 flex flex-col overflow-hidden"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
      >
        {/* 상단: 뒤로가기 */}
        <div className="px-8 pt-4 pb-2">
          <button
            onClick={exitChatMode}
            className="flex items-center gap-2 text-white/50 hover:text-white/80 transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>돌아가기</span>
          </button>
        </div>

        {/* 중앙: 채팅 흐름 */}
        <ChatFlow />

        {/* 하단: 입력창 */}
        <motion.section
          className="px-8 py-4"
          layout
          transition={layoutTransition}
        >
          <div className="max-w-3xl mx-auto">
            <SpotlightInput />
          </div>
        </motion.section>
      </motion.div>
    );
  }

  // 기본 모드
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* 상단: 추천 명령어 */}
      <section className="flex-1 flex items-end justify-center px-8 pb-6 overflow-hidden">
        <ScrollArea className="w-full max-h-full">
          <div className="pb-2">
            <CommandSuggestions />
          </div>
        </ScrollArea>
      </section>

      {/* 중앙: Spotlight 입력 영역 */}
      <motion.section
        className="px-8 py-6"
        layout
        transition={layoutTransition}
      >
        <div className="max-w-3xl mx-auto">
          <SpotlightInput />

          {/* Interactive Form (조건부 렌더링) */}
          <AnimatePresence mode="wait">
            {activeCommand && <InteractiveForm command={activeCommand} />}
          </AnimatePresence>
        </div>
      </motion.section>

      {/* 하단: 명령 히스토리 */}
      <section className="flex-1 overflow-hidden px-8 pt-6">
        <ScrollArea className="h-full">
          <div className="pb-6">
            <CommandHistory />
          </div>
        </ScrollArea>
      </section>
    </div>
  );
}
