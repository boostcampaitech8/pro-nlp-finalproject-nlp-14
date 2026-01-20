// 레이아웃 모드 설정
import type { LayoutMode, LayoutConfig } from '@/app/types/conversation';

// 레이아웃 모드별 설정
export const LAYOUT_CONFIGS: Record<LayoutMode, LayoutConfig> = {
  // 중앙 영역만 채팅으로 변환 (사이드바 유지)
  'center-only': {
    showLeftSidebar: true,
    showRightSidebar: true,
    centerClass: 'flex-1',
    conversationMaxWidth: 'max-w-3xl',
  },
  // 전체 화면 채팅 (모든 사이드바 숨김)
  fullscreen: {
    showLeftSidebar: false,
    showRightSidebar: false,
    centerClass: 'w-full',
    conversationMaxWidth: 'max-w-4xl',
  },
  // 중앙+우측 병합 (좌측만 유지)
  'center-right-merged': {
    showLeftSidebar: true,
    showRightSidebar: false,
    centerClass: 'flex-1',
    conversationMaxWidth: 'max-w-5xl',
  },
};

// 사이드바 너비 상수
export const SIDEBAR_WIDTHS = {
  left: 280,
  right: 400,
} as const;

// 애니메이션 지속 시간
export const LAYOUT_TRANSITION_DURATION = 0.35;
