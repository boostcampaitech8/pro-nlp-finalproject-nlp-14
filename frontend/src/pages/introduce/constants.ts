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
  headline: '회의의 진실을 관리하세요',
  subtext:
    'Git이 코드의 진실을 관리하듯, Mit은 조직 회의의 모든 결정과 맥락을 추적합니다.',
  typewriterText: '@부덕이 오늘 회의 요약해줘',
  aiResponse:
    '오늘 회의에서 총 3건의 결정 사항이 있었습니다. 가장 중요한 안건은 Q1 로드맵 확정이며, 담당자는 김개발님으로 배정되었습니다.',
  ctaPrimary: '시작하기',
  ctaSecondary: '더 알아보기',
} as const;

export const PROBLEM = {
  headline: '회의 끝나면, 결정도 끝나시나요?',
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
      description: '동일한 안건이 반복 논의됩니다',
    },
  ] satisfies PainPoint[],
} as const;

export const FEATURES = {
  headline: '핵심 기능',
  cards: [
    {
      icon: Video,
      title: '실시간 AI 회의',
      description:
        'AI가 회의에 참여하여 실시간으로 내용을 분석하고, 핵심 논점을 자동으로 감지합니다.',
      variant: 'primary',
    },
    {
      icon: Command,
      title: 'Spotlight AI 에이전트',
      description:
        '자연어로 회의 내용을 검색하고, AI 에이전트가 즉시 답변합니다.',
      variant: 'accent',
    },
    {
      icon: FileText,
      title: '자동 회의록',
      description:
        '회의가 끝나면 자동으로 구조화된 회의록이 생성됩니다. 결정사항, 액션아이템까지.',
      variant: 'default',
    },
    {
      icon: GitBranch,
      title: '조직 지식 그래프',
      description:
        '회의 간 연결고리를 추적하고, 조직의 의사결정 히스토리를 시각화합니다.',
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
  headline: '왜 Mit인가',
  rows: [
    {
      category: '회의 후 결과물',
      general: '수동 회의록 또는 없음',
      mit: 'AI 자동 생성 구조화된 회의록',
    },
    {
      category: '의사결정 추적',
      general: '개인 기억에 의존',
      mit: '모든 결정의 맥락과 히스토리 보존',
    },
    {
      category: '조직 지식',
      general: '담당자 퇴사 시 소실',
      mit: '지식 그래프로 영구 보존',
    },
    {
      category: '인터페이스',
      general: '복잡한 대시보드',
      mit: 'Spotlight 자연어 검색',
    },
  ] satisfies ComparisonRow[],
} as const;

export const TEAM = {
  headline: '팀과 함께 시작하세요',
  subtext: '팀원을 초대하고 함께 회의의 가치를 극대화하세요.',
  features: [
    { label: '팀 관리' },
    { label: '초대 링크' },
    { label: '권한 설정' },
    { label: '댓글 & 제안' },
    { label: '실시간 협업' },
  ] satisfies TeamFeature[],
} as const;

export const CTA = {
  headline: '첫 번째 회의를 커밋하세요',
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
  'cta',
] as const;
