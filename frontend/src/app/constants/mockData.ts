// Mock 데이터 - Mit Agent 시연용
import type { SessionContext } from '@/app/types/command';

// 프로젝트 X 예산 타임라인 데이터
export const PROJECT_X_BUDGET_TIMELINE = [
  {
    date: '2025-11-01',
    value: '3,000만원',
    author: '김OO',
    reason: '킥오프 - 초기 예산 제안',
    meetingId: 'meeting-001',
  },
  {
    date: '2025-11-15',
    value: '4,500만원',
    author: '이OO',
    reason: '범위 확대로 인한 조정',
    meetingId: 'meeting-002',
  },
  {
    date: '2025-11-22',
    value: '5,000만원',
    author: '박OO',
    reason: '+500만원 예비비 (불확실성 대비)',
    meetingId: 'meeting-003',
  },
  {
    date: '2025-12-30',
    value: '5,000만원',
    author: '전원 합의',
    reason: '최종 확정',
    meetingId: 'meeting-004',
    isFinal: true,
  },
];

// 오늘 일정 Mock
export const TODAY_SCHEDULE = [
  {
    id: 'meeting-today-1',
    title: '주간 팀 미팅',
    time: '10:00 - 11:00',
    participants: ['개발팀 전원 (8명)'],
    location: '회의실 A',
  },
  {
    id: 'meeting-today-2',
    title: '프로젝트 리뷰',
    time: '14:00 - 15:30',
    participants: ['김OO', '이OO', '박OO'],
    location: '회의실 B',
  },
];

// Action Items Mock
export const ACTION_ITEMS = [
  {
    id: 'action-1',
    title: 'UI 디자인 검토',
    assignee: '김OO',
    dueDate: '1/20',
    completed: false,
  },
  {
    id: 'action-2',
    title: 'API 스펙 정의',
    assignee: '이OO',
    dueDate: '1/22',
    completed: false,
  },
  {
    id: 'action-3',
    title: '예산 승인 요청',
    assignee: '박OO',
    dueDate: '1/18',
    completed: true,
  },
];

// 팀 현황 Mock
export const TEAM_STATUS = {
  teamName: '개발팀',
  memberCount: 8,
  activeProjects: 3,
  weeklyMeetings: 5,
  recentActivities: [
    '어제: 스프린트 회고 회의',
    '그제: 기술 리뷰 세션',
    '지난주: 신규 입사자 온보딩',
  ],
};

// 컨텍스트 기반 응답 생성 헬퍼
export function getContextAwareResponse(
  command: string,
  context: SessionContext | null
): { shouldUsePreviousContext: boolean; extractedValue?: string } {
  const lowerCommand = command.toLowerCase();

  // "6천만원으로", "올리자" 등 금액 변경 의도 감지
  const amountMatch = command.match(/(\d+천만원|\d+억)/);
  if (amountMatch && context?.target) {
    return {
      shouldUsePreviousContext: true,
      extractedValue: amountMatch[1],
    };
  }

  // "확정해줘" - branchId 필요
  if ((lowerCommand.includes('확정') || lowerCommand.includes('머지') || lowerCommand.includes('merge')) && context?.branchId) {
    return { shouldUsePreviousContext: true };
  }

  return { shouldUsePreviousContext: false };
}

// Branch ID 생성
export function generateBranchId(): string {
  return `branch-${Date.now()}`;
}
