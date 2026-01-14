// 좌측 사이드바 (280px)
import { Logo } from './Logo';
import { CurrentSession } from './CurrentSession';
import { Navigation } from './Navigation';
import { MiniCard } from './MiniCard';
import { ScrollArea } from '@/app/components/ui';

export function LeftSidebar() {
  return (
    <aside className="w-[280px] glass-sidebar flex flex-col border-r border-glass">
      {/* 헤더: 로고 + 현재 세션 */}
      <div className="p-5 border-b border-glass">
        <Logo />
        <CurrentSession />
      </div>

      {/* 네비게이션 */}
      <ScrollArea className="flex-1">
        <nav className="p-4">
          <Navigation />
        </nav>
      </ScrollArea>

      {/* 미니 카드 */}
      <div className="p-3 border-t border-glass">
        <MiniCard />
      </div>
    </aside>
  );
}
