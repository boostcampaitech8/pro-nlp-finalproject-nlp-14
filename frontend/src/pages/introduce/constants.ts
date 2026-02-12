import { Video, Command, FileText, GitBranch, FileX, Search } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface PainPoint {
  icon: LucideIcon;
  title: string;
  description: string;
}

export interface FeatureCard {
  icon: LucideIcon;
  title: string;
  description: string;
  variant: 'primary' | 'accent' | 'default' | 'graph';
}

export interface ComparisonRow {
  category: string;
  general: string;
  mit: string;
}

export interface TeamFeature {
  label: string;
}

export const HERO = {
  headline: '팀의 모든 결정, 놓치지 않게',
  subtext:
    'Mit은 회의 속 결정과 맥락을 자동으로 기록하고, 언제든 다시 찾을 수 있게 합니다.',
  typewriterText: '@부덕이 오늘 회의 요약해줘',
  aiResponse:
    '오늘 회의에서 총 3건의 결정 사항이 있었습니다. 가장 중요한 안건은 Q1 로드맵 확정이며, 담당자는 김개발님으로 배정되었습니다.',
  ctaPrimary: '시작하기',
  ctaSecondary: '더 알아보기',
} as const;

export const PROBLEM = {
  headline: '회의는 잘 끝난 것 같은데...',
  mascotBubble: '이런 경험 있지 않으세요?',
  painPoints: [
    {
      icon: FileX,
      title: '사라지는 회의록',
      description: '회의록은 쓰지만 아무도 다시 보지 않습니다',
    },
    {
      icon: Search,
      title: '추적 불가능한 결정',
      description: '3개월 전 결정이 왜 내려졌는지 아무도 모릅니다',
    },
    {
      icon: GitBranch,
      title: '반복되는 논의',
      description: '같은 안건, 같은 논의, 다른 회의',
    },
  ] satisfies PainPoint[],
} as const;

export const FEATURES = {
  headline: 'Mit이 회의에 들어가면',
  cards: [
    {
      icon: Video,
      title: '실시간 AI 회의',
      description:
        '기록은 걱정 마세요. AI가 실시간으로.',
      variant: 'primary',
    },
    {
      icon: Command,
      title: 'Spotlight AI 에이전트',
      description:
        '기억이 가물가물한 지난 결정 사항, 검색으로 편하게!',
      variant: 'accent',
    },
    {
      icon: FileText,
      title: '자동 회의록',
      description:
        '더 이상 회의록을 쓰지 않아도 됩니다. 결정사항부터 액션아이템까지.',
      variant: 'default',
    },
    {
      icon: GitBranch,
      title: '조직 지식 그래프',
      description:
        '흩어진 회의, 하나의 흐름으로.',
      variant: 'graph',
    },
  ] satisfies FeatureCard[],
} as const;

export const DEMO = {
  headline: 'Spotlight UI 체험',
  messages: [
    {
      role: 'user' as const,
      content: '오늘 회의 요약해줘',
    },
    {
      role: 'ai' as const,
      content:
        '오늘 스프린트 회의에서 논의된 내용을 요약해 드릴게요.\n\n핵심 결정사항 3건이 확인되었습니다:',
    },
    {
      role: 'ai' as const,
      content:
        '• **Q1 로드맵 확정** — 담당: 김개발 (1/15까지)\n• **디자인 시스템 v2 마이그레이션** — 담당: 이디자인 (1/20까지)\n• **성능 최적화 스프린트** — 담당: 박백엔드 (1/25까지)',
    },
  ],
} as const;

export const DIFFERENTIATION = {
  headline: '같은 회의, 다른 결과',
  rows: [
    {
      category: '회의 후 결과물',
      general: '수동 회의록 또는 없음',
      mit: 'AI가 정리한 회의록, 바로 공유',
    },
    {
      category: '의사결정 추적',
      general: '개인 기억에 의존',
      mit: '왜 그렇게 결정했는지, 언제든 검색',
    },
    {
      category: '조직 지식',
      general: '담당자 퇴사 시 소실',
      mit: '사람이 바뀌어도 맥락은 남게',
    },
    {
      category: '인터페이스',
      general: '복잡한 대시보드',
      mit: '물어보면 답하는 Spotlight',
    },
  ] satisfies ComparisonRow[],
} as const;

export const TEAM = {
  headline: '팀과 함께 시작하세요',
  subtext: '',
  features: [
    { label: '팀 관리' },
    { label: '초대 링크' },
    { label: '권한 설정' },
    { label: '댓글 & 제안' },
    { label: '실시간 협업' },
  ] satisfies TeamFeature[],
} as const;

export const CTA = {
  headline: '첫 번째 회의를 기록하세요',
  ctaPrimary: '무료로 시작하기',
  loginText: '이미 계정이 있으신가요?',
  loginLink: '로그인',
} as const;

export const SECTION_IDS = [
  'hero',
  'problem',
  'features',
  'demo',
  'differentiation',
  'team',
] as const;
