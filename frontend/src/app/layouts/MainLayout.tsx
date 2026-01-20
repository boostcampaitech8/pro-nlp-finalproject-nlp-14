// 메인 레이아웃 (3단 구조)
// 좌측 사이드바 (280px) | 중앙 콘텐츠 (flex) | 우측 사이드바 (400px)
import { Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { LeftSidebar } from '@/app/components/sidebar';
import { RightSidebar } from '@/app/components/preview';
import { MeetingModal } from '@/app/components/meeting';
import { TooltipProvider } from '@/app/components/ui';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { useConversationStore } from '@/app/stores/conversationStore';
import { LAYOUT_CONFIGS, SIDEBAR_WIDTHS, LAYOUT_TRANSITION_DURATION } from '@/app/constants/layoutConfig';
import { cn } from '@/lib/utils';

export function MainLayout() {
  const { isOpen, initialData, closeModal } = useMeetingModalStore();
  const { isConversationActive, layoutMode } = useConversationStore();

  // 대화 모드일 때만 레이아웃 설정 적용
  const config = isConversationActive ? LAYOUT_CONFIGS[layoutMode] : LAYOUT_CONFIGS['center-only'];

  return (
    <TooltipProvider>
      <div className="h-screen w-screen gradient-bg flex overflow-hidden">
        {/* 좌측 사이드바 (280px) - 조건부 */}
        <AnimatePresence mode="wait">
          {config.showLeftSidebar && (
            <motion.div
              key="left-sidebar"
              initial={{ width: SIDEBAR_WIDTHS.left, opacity: 1 }}
              animate={{ width: SIDEBAR_WIDTHS.left, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: LAYOUT_TRANSITION_DURATION, ease: [0.32, 0.72, 0, 1] }}
              className="flex-shrink-0 overflow-hidden"
            >
              <LeftSidebar />
            </motion.div>
          )}
        </AnimatePresence>

        {/* 중앙 콘텐츠 영역 */}
        <motion.main
          className={cn('flex-1 flex flex-col min-w-0 overflow-hidden', config.centerClass)}
          layout
          transition={{ duration: LAYOUT_TRANSITION_DURATION, ease: [0.32, 0.72, 0, 1] }}
        >
          <Outlet />
        </motion.main>

        {/* 우측 사이드바 (400px) - 조건부 */}
        <AnimatePresence mode="wait">
          {config.showRightSidebar && (
            <motion.div
              key="right-sidebar"
              initial={{ width: SIDEBAR_WIDTHS.right, opacity: 1 }}
              animate={{ width: SIDEBAR_WIDTHS.right, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: LAYOUT_TRANSITION_DURATION, ease: [0.32, 0.72, 0, 1] }}
              className="flex-shrink-0 overflow-hidden"
            >
              <RightSidebar />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 회의 생성 모달 */}
      <MeetingModal
        open={isOpen}
        onOpenChange={(open) => !open && closeModal()}
        initialData={initialData || undefined}
      />
    </TooltipProvider>
  );
}
