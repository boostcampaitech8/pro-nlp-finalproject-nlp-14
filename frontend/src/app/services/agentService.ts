// 에이전트 서비스 (Mock API)
// 실제 백엔드 API 연동 전까지 사용하는 Mock 데이터
//
// ============================================================
// Mock 테스트 시나리오 가이드
// ============================================================
//
// [1] 명령 모드 (processCommand) - 키워드 기반 응답 분기
//
//   입력 예시                     | 매칭 키워드           | 응답 타입 | 동작
//   ----------------------------|---------------------|----------|------------------
//   "새 회의 시작"                | 회의+시작/새/만들, 미팅 | modal    | 회의 생성 모달 표시
//   "회의록 검색"                 | 검색, 찾             | form     | 검색 조건 폼 표시
//   "예산 변경"                   | 예산 (이력 제외)      | form     | 예산 변경 폼 표시
//   "예산 이력 조회"              | blame, 이력, 히스토리 | direct   | 히스토리 카드 표시
//   "오늘 일정"                   | 일정, 스케줄, 오늘    | direct   | 히스토리 카드 표시
//   "팀 현황"                     | 팀+현황/상태          | direct   | 히스토리 카드 표시
//   "지난주 회의 요약해줘"         | 요약, 정리, 알려, 질문 | direct   | -> 채팅 모드 진입
//   (매칭 없는 입력)              | -                   | form     | 기본 상세입력 폼 표시
//
// [2] 채팅 모드 (processChatMessage) - 채팅 모드 진입 후 대화 흐름
//
//   채팅 모드 진입 조건:
//     processCommand에서 type='direct' 응답 시 useCommand 훅이 채팅 모드를 활성화한다.
//     이후 입력은 processChatMessage를 통해 처리된다.
//
//   테스트 시나리오:
//
//   Step 1 - 채팅 모드 진입
//     입력: "지난주 개발팀 회의 요약해줘"
//     결과: 채팅 모드 전환 + 회의 요약 응답 (MOCK_MEETING_SUMMARY)
//            일시, 참석자, 주요 안건 3건, 결정 사항 2건, 액션 아이템 2건
//
//   Step 2 - 후속 질문 (결정 사항 상세)
//     입력: "결정 사항 더 자세히 알려줘"
//     매칭: 결정 + (자세/상세/더)
//     결과: CI/CD 파이프라인 개선, 코드 리뷰 시간 변경 상세 (MOCK_DECISION_DETAIL)
//
//   Step 3 - 매칭 안 되는 후속 질문
//     입력: "다음 회의는 언제야?"
//     결과: "해당 내용은 아직 확인 중입니다. 다른 질문이 있으신가요?"
//
//   채팅 모드 종료:
//     - ESC 키 또는 뒤로가기 버튼(ArrowLeft) 클릭 -> 기본 Spotlight UI 복귀
//
// ============================================================

import type { ActiveCommand, AgentResponse, CommandField, ModalData } from '@/app/types/command';
import { API_DELAYS } from '@/app/constants';

// Mock 응답 정의
interface MockResponse {
  type: 'form' | 'direct' | 'modal';
  title?: string;
  description?: string;
  icon?: string;
  fields?: CommandField[];
  message?: string;
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
  },

  // 일정 조회
  schedule: {
    type: 'direct',
    message: '오늘 예정된 회의가 2건 있습니다.',
  },

  // 팀 현황
  team_status: {
    type: 'direct',
    message: '팀 현황을 불러왔습니다.',
  },

  // 회의 요약/질문 (채팅 모드 진입)
  meeting_chat: {
    type: 'direct',
    message: '채팅 모드로 전환합니다.',
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

  // 회의 요약/질문 (채팅 모드 진입 대상)
  if (
    lowerCommand.includes('요약') ||
    lowerCommand.includes('정리') ||
    lowerCommand.includes('알려') ||
    lowerCommand.includes('질문')
  ) {
    return MOCK_RESPONSES.meeting_chat;
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

// 채팅 Mock 응답
const MOCK_MEETING_SUMMARY = `지난주 개발팀 회의 요약입니다.

**일시**: 2024년 1월 22일 (월) 14:00-15:30
**참석자**: 김OO, 이OO, 박OO, 최OO

**주요 안건**:
1. Sprint 12 회고 - 배포 지연 원인 분석 완료
2. API v2 마이그레이션 - 다음 주 수요일까지 완료 목표
3. 모니터링 대시보드 - Grafana 설정 담당자 배정 (이OO)

**결정 사항**:
- CI/CD 파이프라인 개선 작업 우선순위 상향
- 주간 코드 리뷰 시간 화요일 11시로 변경

**액션 아이템**:
- 박OO: API v2 엔드포인트 목록 정리 (1/24까지)
- 최OO: 모니터링 알림 규칙 초안 작성 (1/26까지)`;

const MOCK_DECISION_DETAIL = `결정 사항 상세 내용입니다.

**1. CI/CD 파이프라인 개선 (우선순위 상향)**
- 현재 배포 소요 시간: 평균 45분
- 목표: 15분 이내로 단축
- 담당: 김OO (리드), 박OO (서포트)
- 기한: 2월 첫째 주

**2. 주간 코드 리뷰 시간 변경**
- 기존: 수요일 14시
- 변경: 화요일 11시
- 사유: 수요일 오후 회의 충돌 빈번
- 적용 시점: 다음 주부터`;

const MOCK_DEFAULT_FOLLOWUP = '해당 내용은 아직 확인 중입니다. 다른 질문이 있으신가요?';

// 채팅 메시지 매칭
function matchChatResponse(message: string): string {
  const lower = message.toLowerCase();

  // 회의 요약 관련
  if (lower.includes('회의') && (lower.includes('요약') || lower.includes('정리') || lower.includes('내용'))) {
    return MOCK_MEETING_SUMMARY;
  }

  // 결정 사항 상세
  if (lower.includes('결정') && (lower.includes('자세') || lower.includes('상세') || lower.includes('더'))) {
    return MOCK_DECISION_DETAIL;
  }

  return MOCK_DEFAULT_FOLLOWUP;
}

export const agentService = {
  /**
   * 명령어 처리
   * @param command 사용자가 입력한 명령어
   * @returns AgentResponse
   */
  async processCommand(command: string): Promise<AgentResponse> {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.COMMAND_PROCESS));

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
    _fields: Record<string, string>
  ): Promise<AgentResponse> {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.FORM_SUBMIT));

    return {
      type: 'direct',
      message: `${commandTitle}이(가) 성공적으로 실행되었습니다.`,
    };
  },

  /**
   * 채팅 메시지 처리
   * @param message 사용자 입력 메시지
   * @returns 에이전트 응답 텍스트
   */
  async processChatMessage(message: string): Promise<string> {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.COMMAND_PROCESS));
    return matchChatResponse(message);
  },

  /**
   * 추천 명령어 조회
   * @returns Suggestion[]
   */
  async getSuggestions() {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.SUGGESTIONS_FETCH));

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
