// 메인 레이아웃 (2단 구조)
// 좌측 사이드바 (280px) | 중앙 콘텐츠 (flex)
import { Outlet } from 'react-router-dom';
import { LeftSidebar } from '@/app/components/sidebar';
import { MeetingModal } from '@/app/components/meeting';
import { TooltipProvider } from '@/app/components/ui';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';

export function MainLayout() {
  const { isOpen, initialData, closeModal } = useMeetingModalStore();

  return (
    <TooltipProvider>
      <div className="h-screen w-screen gradient-bg flex overflow-hidden">
        {/* 좌측 사이드바 (280px) */}
        <LeftSidebar />

        {/* 중앙 콘텐츠 영역 */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <Outlet />
        </main>

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
