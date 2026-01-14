// 에이전트 서비스 (Mock API)
// 실제 백엔드 API 연동 전까지 사용하는 Mock 데이터

import type { ActiveCommand, AgentResponse, CommandField, ModalData } from '@/app/types/command';

// Mock 응답 정의
interface MockResponse {
  type: 'form' | 'direct' | 'modal';
  title?: string;
  description?: string;
  icon?: string;
  fields?: CommandField[];
  message?: string;
  previewType?: string;
  previewContent?: string;
  modalData?: ModalData;
}

const MOCK_RESPONSES: Record<string, MockResponse> = {
  // 회의 관련 - 모달로 처리
  meeting_create: {
    type: 'modal',
    modalData: {
      modalType: 'meeting',
    },
  },

  // 검색 관련
  search: {
    type: 'form',
    title: '회의록 검색',
    description: '검색 조건을 입력해주세요',
    icon: '🔍',
    fields: [
      {
        id: 'keyword',
        label: '검색어',
        type: 'text',
        placeholder: '찾고 싶은 키워드',
        required: true,
      },
      {
        id: 'dateRange',
        label: '검색 기간',
        type: 'select',
        options: ['최근 1주일', '최근 1개월', '최근 3개월', '전체 기간'],
      },
      {
        id: 'team',
        label: '팀 필터',
        type: 'select',
        options: ['전체', '개발팀', '디자인팀', '마케팅팀'],
      },
    ],
  },

  // 예산 관련 (기획서 예시)
  budget: {
    type: 'form',
    title: '예산 변경 제안',
    description: '예산 변경 내용을 입력해주세요',
    icon: '💰',
    fields: [
      {
        id: 'amount',
        label: '변경 금액',
        type: 'text',
        placeholder: '예: 6,000만원',
        required: true,
      },
      {
        id: 'reason',
        label: '변경 사유',
        type: 'textarea',
        placeholder: '예산 변경이 필요한 이유를 설명해주세요',
        required: true,
      },
      {
        id: 'reviewer',
        label: '리뷰어 지정',
        type: 'select',
        options: ['김OO', '이OO', '박OO', '최OO'],
      },
    ],
  },

  // Blame 이력 조회
  blame: {
    type: 'direct',
    message: '예산 변경 이력을 조회했습니다.',
    previewType: 'document',
    previewContent: `## 예산 변경 이력

| 날짜 | 금액 | 변경자 | 사유 |
|------|------|--------|------|
| 2026-01-10 | 5,000만원 | 김OO | 최종 확정 |
| 2026-01-05 | 4,500만원 | 이OO | 범위 확대로 인한 조정 |
| 2026-01-01 | 3,000만원 | 박OO | 초기 제안 |

총 3건의 변경 이력이 있습니다.`,
  },

  // 일정 조회
  schedule: {
    type: 'direct',
    message: '오늘 예정된 회의가 2건 있습니다.',
    previewType: 'meeting',
    previewContent: `## 오늘의 일정

### 1. 주간 팀 미팅
- 시간: 10:00 - 11:00
- 참여자: 개발팀 전원 (8명)
- 장소: 회의실 A

### 2. 프로젝트 리뷰
- 시간: 14:00 - 15:30
- 참여자: 김OO, 이OO, 박OO
- 장소: 회의실 B`,
  },

  // 팀 현황
  team_status: {
    type: 'direct',
    message: '팀 현황을 불러왔습니다.',
    previewType: 'document',
    previewContent: `## 팀 현황 요약

### 개발팀
- 총 인원: 8명
- 진행 중인 프로젝트: 3개
- 이번 주 회의: 5회

### 최근 활동
- 어제: 스프린트 회고 회의
- 그제: 기술 리뷰 세션
- 지난주: 신규 입사자 온보딩`,
  },

  // 기본 응답
  default: {
    type: 'form',
    title: '명령 상세 입력',
    description: '추가 정보가 필요합니다',
    icon: '📝',
    fields: [
      {
        id: 'detail',
        label: '상세 내용',
        type: 'textarea',
        placeholder: '원하시는 작업을 자세히 설명해주세요',
        required: true,
      },
    ],
  },
};

// 키워드 기반 응답 매칭
function matchCommand(command: string): MockResponse {
  const lowerCommand = command.toLowerCase();

  // 회의 시작/생성
  if (
    (lowerCommand.includes('회의') && (lowerCommand.includes('시작') || lowerCommand.includes('새') || lowerCommand.includes('만들'))) ||
    lowerCommand.includes('미팅')
  ) {
    return MOCK_RESPONSES.meeting_create;
  }

  // 검색
  if (lowerCommand.includes('검색') || lowerCommand.includes('찾')) {
    return MOCK_RESPONSES.search;
  }

  // 예산
  if (lowerCommand.includes('예산') && !lowerCommand.includes('이력')) {
    return MOCK_RESPONSES.budget;
  }

  // Blame / 이력
  if (lowerCommand.includes('blame') || lowerCommand.includes('이력') || lowerCommand.includes('히스토리')) {
    return MOCK_RESPONSES.blame;
  }

  // 일정
  if (lowerCommand.includes('일정') || lowerCommand.includes('스케줄') || lowerCommand.includes('오늘')) {
    return MOCK_RESPONSES.schedule;
  }

  // 팀 현황
  if (lowerCommand.includes('팀') && (lowerCommand.includes('현황') || lowerCommand.includes('상태'))) {
    return MOCK_RESPONSES.team_status;
  }

  return MOCK_RESPONSES.default;
}

export const agentService = {
  /**
   * 명령어 처리
   * @param command 사용자가 입력한 명령어
   * @returns AgentResponse
   */
  async processCommand(command: string): Promise<AgentResponse> {
    // API 호출 시뮬레이션 (500ms 딜레이)
    await new Promise((resolve) => setTimeout(resolve, 500));

    const matched = matchCommand(command);

    // 모달 타입 응답 처리
    if (matched.type === 'modal' && matched.modalData) {
      return {
        type: 'modal',
        modalData: matched.modalData,
      };
    }

    // 폼 타입 응답 처리
    if (matched.type === 'form' && matched.fields) {
      const activeCommand: ActiveCommand = {
        id: `cmd-${Date.now()}`,
        type: 'user-command',
        title: matched.title || '명령 실행',
        description: matched.description || '',
        icon: matched.icon,
        fields: matched.fields,
      };

      return {
        type: 'form',
        command: activeCommand,
      };
    }

    // 직접 응답 처리
    return {
      type: 'direct',
      message: matched.message || `"${command}" 명령을 처리했습니다.`,
      previewData: matched.previewContent
        ? {
            type: matched.previewType || 'command-result',
            title: matched.title || command,
            content: matched.previewContent,
          }
        : undefined,
    };
  },

  /**
   * Form 제출 처리
   * @param commandId 명령 ID
   * @param commandTitle 명령 제목
   * @param fields 필드 값들
   * @returns AgentResponse
   */
  async submitForm(
    _commandId: string,
    commandTitle: string,
    fields: Record<string, string>
  ): Promise<AgentResponse> {
    // API 호출 시뮬레이션 (800ms 딜레이)
    await new Promise((resolve) => setTimeout(resolve, 800));

    // 필드 값 포맷팅
    const fieldSummary = Object.entries(fields)
      .filter(([, value]) => value)
      .map(([key, value]) => `- **${key}**: ${value}`)
      .join('\n');

    return {
      type: 'direct',
      message: `${commandTitle}이(가) 성공적으로 실행되었습니다.`,
      previewData: {
        type: 'command-result',
        title: `${commandTitle} 결과`,
        content: `## 실행 완료

${commandTitle}이(가) 성공적으로 처리되었습니다.

### 입력된 정보
${fieldSummary || '(입력된 정보 없음)'}

### 처리 시간
${new Date().toLocaleString('ko-KR')}`,
      },
    };
  },

  /**
   * 추천 명령어 조회
   * @returns Suggestion[]
   */
  async getSuggestions() {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, 200));

    return [
      {
        id: '1',
        title: '새 회의 시작',
        description: '팀원들과 새로운 회의를 시작합니다',
        icon: '🎯',
        command: '새 회의 시작',
        category: 'meeting' as const,
      },
      {
        id: '2',
        title: '지난 회의록 검색',
        description: '이전 회의 내용을 검색합니다',
        icon: '🔍',
        command: '회의록 검색',
        category: 'search' as const,
      },
      {
        id: '3',
        title: '오늘 일정 확인',
        description: '오늘 예정된 회의를 확인합니다',
        icon: '📅',
        command: '오늘 일정',
        category: 'action' as const,
      },
      {
        id: '4',
        title: '팀 현황 보기',
        description: '팀 멤버와 활동 현황을 확인합니다',
        icon: '👥',
        command: '팀 현황',
        category: 'action' as const,
      },
    ];
  },
};
