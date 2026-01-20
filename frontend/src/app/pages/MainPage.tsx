// 새 서비스 메인 페이지 (Spotlight UI)
import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCommandStore } from '@/app/stores/commandStore';
import { useConversationStore } from '@/app/stores/conversationStore';
import { agentService } from '@/app/services/agentService';
import {
  SpotlightInput,
  CommandSuggestions,
  CommandHistory,
  InteractiveForm,
} from '@/app/components/spotlight';
import { ConversationContainer } from '@/app/components/conversation';
import { ScrollArea } from '@/app/components/ui';
import { modeTransitionVariants } from '@/app/constants/animations';

export function MainPage() {
  const { activeCommand, setSuggestions } = useCommandStore();
  const { isConversationActive } = useConversationStore();

  // 추천 명령어 로드
  useEffect(() => {
    agentService.getSuggestions().then(setSuggestions);
  }, [setSuggestions]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <AnimatePresence mode="wait">
        {isConversationActive ? (
          // 대화 모드
          <ConversationContainer key="conversation" />
        ) : (
          // 기본 모드
          <motion.div
            key="normal"
            variants={modeTransitionVariants.historyBlur}
            initial="initial"
            animate="animate"
            exit="exit"
            className="flex-1 flex flex-col overflow-hidden"
          >
            {/* 상단: 추천 명령어 */}
            <section className="flex-1 flex items-end justify-center px-8 pb-6 overflow-hidden">
              <ScrollArea className="w-full max-h-full">
                <div className="pb-2">
                  <CommandSuggestions />
                </div>
              </ScrollArea>
            </section>

            {/* 중앙: Spotlight 입력 영역 */}
            <section className="px-8 py-6">
              <div className="max-w-3xl mx-auto">
                <SpotlightInput />

                {/* Interactive Form (조건부 렌더링) */}
                <AnimatePresence mode="wait">
                  {activeCommand && <InteractiveForm command={activeCommand} />}
                </AnimatePresence>
              </div>
            </section>

            {/* 하단: 명령 히스토리 */}
            <section className="flex-1 overflow-hidden px-8 pt-6">
              <ScrollArea className="h-full">
                <div className="pb-6">
                  <CommandHistory />
                </div>
              </ScrollArea>
            </section>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
