// 새 서비스 메인 페이지 (Spotlight UI)
import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useCommandStore } from '@/app/stores/commandStore';
import { agentService } from '@/app/services/agentService';
import {
  SpotlightInput,
  CommandSuggestions,
  CommandHistory,
  ChatFlow,
  PendingMessageQueue,
} from '@/app/components/spotlight';
import { ScrollArea } from '@/app/components/ui';

const layoutTransition = {
  duration: 0.4,
  ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
};

export function MainPage() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const { isChatMode, setSuggestions, setCurrentSession, loadSessionMessages } = useCommandStore();
  const exitChatMode = useCommandStore((s) => s.exitChatMode);
  const enterChatMode = useCommandStore((s) => s.enterChatMode);

  // 추천 명령어 로드
  useEffect(() => {
    agentService.getSuggestions().then(setSuggestions);
  }, [setSuggestions]);

  // URL → State 동기화 (단방향)
  useEffect(() => {
    const state = useCommandStore.getState();

    if (!urlSessionId) {
      // 홈으로 이동: 채팅 모드 종료
      if (state.currentSessionId) {
        exitChatMode();
      }
      return;
    }

    // 같은 세션이 이미 로드되어 있으면 스킵
    if (urlSessionId === state.currentSessionId) {
      // 새로고침 시 채팅 모드 복원
      if (!state.isChatMode) {
        enterChatMode();
      }
      return;
    }

    // 새로운 세션으로 전환
    setCurrentSession(urlSessionId);
    loadSessionMessages(urlSessionId);
    enterChatMode();
  }, [urlSessionId, exitChatMode, setCurrentSession, loadSessionMessages, enterChatMode]);

  // 채팅 모드 종료 + URL 홈으로 이동
  const handleExitChatMode = () => {
    exitChatMode();
    navigate('/', { replace: true });
  };

  // ESC 키로 채팅 모드 종료
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isChatMode) {
        handleExitChatMode();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isChatMode]);

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
            onClick={handleExitChatMode}
            className="flex items-center gap-2 text-white/50 hover:text-white/80 transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>돌아가기</span>
          </button>
        </div>

        {/* 중앙: 채팅 흐름 */}
        <ChatFlow />

        {/* 하단: 대기 메시지 + 입력창 */}
        <motion.section
          className="px-8 py-4"
          layout
          transition={layoutTransition}
        >
          <div className="max-w-3xl mx-auto">
            <PendingMessageQueue />
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
