// 새 서비스 메인 페이지 (Spotlight UI)
import { AnimatePresence } from 'framer-motion';
import { useCommandStore } from '@/app/stores/commandStore';
import {
  SpotlightInput,
  CommandSuggestions,
  CommandHistory,
  InteractiveForm,
} from '@/app/components/spotlight';
import { ScrollArea } from '@/app/components/ui';

export function MainPage() {
  const { activeCommand } = useCommandStore();

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
      <section className="px-8 py-6 bg-black/20 border-y border-glass">
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
    </div>
  );
}
