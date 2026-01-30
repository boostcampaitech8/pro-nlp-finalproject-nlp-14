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
//   "새 회의 시작"                | 회의+시작/새/만들, 미팅 | plan     | 회의 생성 계획서
//   "회의록 검색"                 | 검색, 찾             | plan     | 검색 조건 계획서
//   "예산 변경"                   | 예산 (이력 제외)      | plan     | 예산 변경 계획서
//   "예산 이력 조회"              | blame, 이력, 히스토리 | text     | 이력 텍스트 응답
//   "오늘 일정"                   | 일정, 스케줄, 오늘    | text     | 일정 텍스트 응답
//   "팀 현황"                     | 팀+현황/상태          | text     | 현황 텍스트 응답
//   "지난주 회의 요약해줘"         | 요약, 정리, 알려, 질문 | text     | 회의 요약 텍스트
//   (매칭 없는 입력)              | -                   | plan     | 기본 상세입력 계획서
//
// [2] 채팅 모드 (processChatMessage) - 채팅 모드 진입 후 대화 흐름
//
//   모든 명령이 채팅 모드로 진입한다.
//   후속 입력은 processChatMessage를 통해 처리된다.
//
//   테스트 시나리오:
//
//   Step 1 - 채팅 모드 진입
//     입력: "지난주 개발팀 회의 요약해줘"
//     결과: 채팅 모드 전환 + 회의 요약 응답 (MOCK_MEETING_SUMMARY)
//
//   Step 2 - 후속 질문 (결정 사항 상세)
//     입력: "결정 사항 더 자세히 알려줘"
//     매칭: 결정 + (자세/상세/더)
//     결과: 상세 결정 사항 텍스트
//
//   Step 3 - 승인 흐름
//     입력: "승인합니다"
//     결과: 이전 plan 명령에 대한 완료 응답
//
//   채팅 모드 종료:
//     - ESC 키 또는 뒤로가기 버튼 -> 기본 Spotlight UI 복귀
//
// ============================================================

import type { AgentResponse } from '@/app/types/command';
import { API_DELAYS } from '@/app/constants';

// Mock 응답 정의
interface MockResponse {
  type: 'text' | 'plan';
  message: string;
}

const MOCK_RESPONSES: Record<string, MockResponse> = {
  // 회의 관련 - plan 계획서
  meeting_create: {
    type: 'plan',
    message: `회의 생성과 관련된 계획서입니다.
==nlp-14 team== 내부에서 ==금일 5시== 회의 예정입니다.
회의에서 이야기할 내용은
==아젠다1, 아젠다2==
입니다.
<주의사항>
==회의 전 관련 자료 숙지 필요합니다==`,
  },

  // 검색 관련 - plan 계획서
  search: {
    type: 'plan',
    message: `회의록 검색 계획서입니다.
검색어: ==키워드를 입력해주세요==
검색 기간: ==최근 1주일==
팀 필터: ==전체==`,
  },

  // 예산 관련 - plan 계획서
  budget: {
    type: 'plan',
    message: `예산 변경 제안 계획서입니다.
변경 금액: ==6,000만원==
변경 사유: ==예산 변경이 필요한 이유를 설명해주세요==
리뷰어: ==김OO==`,
  },

  // Blame 이력 조회 - text
  blame: {
    type: 'text',
    message: '예산 변경 이력을 조회했습니다.',
  },

  // 일정 조회 - text
  schedule: {
    type: 'text',
    message: '오늘 예정된 회의가 2건 있습니다.',
  },

  // 팀 현황 - text
  team_status: {
    type: 'text',
    message: '팀 현황을 불러왔습니다.',
  },

  // 회의 요약/질문 - text (채팅 모드 진입)
  meeting_chat: {
    type: 'text',
    message: '채팅 모드로 전환합니다.',
  },

  // 기본 응답 - plan 계획서
  default: {
    type: 'plan',
    message: `명령 상세 입력 계획서입니다.
상세 내용: ==원하시는 작업을 자세히 설명해주세요==`,
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

// 승인 Mock 응답
const MOCK_APPROVAL_RESPONSES: Record<string, string> = {
  meeting_create: '회의가 성공적으로 생성되었습니다. 참가자들에게 알림이 전송됩니다.',
  search: '검색을 실행합니다. 결과를 불러오는 중...',
  budget: '예산 변경 제안이 제출되었습니다. 리뷰어에게 알림이 전송됩니다.',
  default: '명령이 성공적으로 실행되었습니다.',
};

const MOCK_DEFAULT_FOLLOWUP = '해당 내용은 아직 확인 중입니다. 다른 질문이 있으신가요?';

// 마지막 명령 키 추적 (승인 시 응답 매칭용)
let lastCommandKey = 'default';

// 채팅 메시지 매칭
function matchChatResponse(message: string): string {
  const lower = message.toLowerCase();

  // 승인 감지
  if (lower.includes('승인')) {
    return MOCK_APPROVAL_RESPONSES[lastCommandKey] || MOCK_APPROVAL_RESPONSES.default;
  }

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

// 명령어에서 키를 결정하는 헬퍼
function resolveCommandKey(command: string): string {
  const lower = command.toLowerCase();

  if (
    (lower.includes('회의') && (lower.includes('시작') || lower.includes('새') || lower.includes('만들'))) ||
    lower.includes('미팅')
  ) {
    return 'meeting_create';
  }
  if (lower.includes('검색') || lower.includes('찾')) return 'search';
  if (lower.includes('예산') && !lower.includes('이력')) return 'budget';
  if (lower.includes('blame') || lower.includes('이력') || lower.includes('히스토리')) return 'blame';
  if (lower.includes('일정') || lower.includes('스케줄') || lower.includes('오늘')) return 'schedule';
  if (lower.includes('팀') && (lower.includes('현황') || lower.includes('상태'))) return 'team_status';
  if (lower.includes('요약') || lower.includes('정리') || lower.includes('알려') || lower.includes('질문')) {
    return 'meeting_chat';
  }
  return 'default';
}

export const agentService = {
  /**
   * 명령어 처리 (항상 text 또는 plan 응답 반환)
   * @param command 사용자가 입력한 명령어
   * @returns AgentResponse
   */
  async processCommand(command: string): Promise<AgentResponse> {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.COMMAND_PROCESS));

    // 마지막 명령 키 기록 (승인 시 참조)
    lastCommandKey = resolveCommandKey(command);

    const matched = matchCommand(command);

    return {
      type: matched.type,
      message: matched.message,
    };
  },

  /**
   * 채팅 메시지 처리
   * @param message 사용자 입력 메시지
   * @returns AgentResponse (항상 text)
   */
  async processChatMessage(message: string): Promise<AgentResponse> {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.COMMAND_PROCESS));
    return {
      type: 'text',
      message: matchChatResponse(message),
    };
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
