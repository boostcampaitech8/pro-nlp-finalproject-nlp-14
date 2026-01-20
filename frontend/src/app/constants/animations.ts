// Framer Motion 애니메이션 variants 정의

import type { Variants } from 'framer-motion';

// 커스텀 이징 함수 (Apple-style)
export const EASING = {
  smooth: [0.32, 0.72, 0, 1],
  bounce: [0.34, 1.56, 0.64, 1],
  decelerate: [0.0, 0.0, 0.2, 1],
  accelerate: [0.4, 0.0, 1, 1],
} as const;

// 모드 전환 애니메이션
export const modeTransitionVariants: Record<string, Variants> = {
  // 입력창 하단 이동
  inputToBottom: {
    initial: { y: 0, opacity: 1 },
    animate: {
      y: 0,
      opacity: 1,
      transition: { duration: 0.4, ease: EASING.smooth },
    },
    exit: {
      y: -20,
      opacity: 0,
      transition: { duration: 0.2, ease: EASING.accelerate },
    },
  },

  // 히스토리/제안 블러 아웃
  historyBlur: {
    initial: { opacity: 1, filter: 'blur(0px)' },
    animate: { opacity: 1, filter: 'blur(0px)' },
    exit: {
      opacity: 0.3,
      filter: 'blur(8px)',
      transition: { duration: 0.3, ease: EASING.smooth },
    },
  },

  // 대화 컨테이너 등장
  conversationContainer: {
    initial: { opacity: 0, y: 20 },
    animate: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.4, ease: EASING.smooth },
    },
    exit: {
      opacity: 0,
      y: -20,
      transition: { duration: 0.2, ease: EASING.accelerate },
    },
  },
};

// 메시지 버블 애니메이션
export const messageVariants: Record<string, Variants> = {
  // 사용자 메시지 (우측에서 등장)
  user: {
    initial: { opacity: 0, x: 20, scale: 0.95 },
    animate: {
      opacity: 1,
      x: 0,
      scale: 1,
      transition: { duration: 0.3, ease: EASING.smooth },
    },
    exit: {
      opacity: 0,
      x: 20,
      scale: 0.95,
      transition: { duration: 0.15, ease: EASING.accelerate },
    },
  },

  // 에이전트 메시지 (좌측에서 등장)
  agent: {
    initial: { opacity: 0, x: -20, scale: 0.95 },
    animate: {
      opacity: 1,
      x: 0,
      scale: 1,
      transition: { duration: 0.3, ease: EASING.smooth },
    },
    exit: {
      opacity: 0,
      x: -20,
      scale: 0.95,
      transition: { duration: 0.15, ease: EASING.accelerate },
    },
  },

  // 시스템 메시지 (페이드 인)
  system: {
    initial: { opacity: 0, y: 10 },
    animate: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.25, ease: EASING.smooth },
    },
    exit: {
      opacity: 0,
      transition: { duration: 0.15 },
    },
  },
};

// 사이드바 애니메이션
export const sidebarVariants: Variants = {
  visible: {
    width: 'auto',
    opacity: 1,
    transition: { duration: 0.35, ease: EASING.smooth },
  },
  hidden: {
    width: 0,
    opacity: 0,
    transition: { duration: 0.35, ease: EASING.smooth },
  },
};

// 폼 애니메이션
export const formVariants: Variants = {
  initial: { opacity: 0, height: 0 },
  animate: {
    opacity: 1,
    height: 'auto',
    transition: { duration: 0.3, ease: EASING.smooth },
  },
  exit: {
    opacity: 0,
    height: 0,
    transition: { duration: 0.2, ease: EASING.accelerate },
  },
};

// 타이핑 인디케이터 애니메이션
export const typingIndicatorVariants: Variants = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: { duration: 0.2 },
  },
  exit: {
    opacity: 0,
    transition: { duration: 0.15 },
  },
};

// 타이핑 도트 애니메이션
export const typingDotVariants: Variants = {
  animate: {
    y: [0, -5, 0],
    transition: {
      duration: 0.6,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
};

// 완료 시 복귀 애니메이션
export const completionVariants: Record<string, Variants> = {
  conversationFade: {
    initial: { opacity: 1, scale: 1 },
    exit: {
      opacity: 0,
      scale: 0.98,
      transition: { duration: 0.25, ease: EASING.accelerate },
    },
  },
  inputToCenter: {
    initial: { y: 100 },
    animate: {
      y: 0,
      transition: { duration: 0.4, ease: EASING.smooth, delay: 0.1 },
    },
  },
  historyRestore: {
    initial: { opacity: 0, filter: 'blur(8px)' },
    animate: {
      opacity: 1,
      filter: 'blur(0px)',
      transition: { duration: 0.3, ease: EASING.smooth, delay: 0.15 },
    },
  },
};

// 리스트 stagger 애니메이션
export const staggerContainerVariants: Variants = {
  animate: {
    transition: {
      staggerChildren: 0.05,
    },
  },
};
