// 명령어 매칭 서비스
// Strategy Pattern을 사용하여 명령어를 매칭

import type { SessionContext } from '@/app/types/command';
import { MOCK_RESPONSES, type MockResponse } from './mockResponses';

// 명령어 패턴 정의
interface CommandPattern {
  keywords: string[];
  excludeKeywords?: string[];
  response: keyof typeof MOCK_RESPONSES;
  // 추가 조건 (context 기반 등)
  condition?: (command: string, context?: SessionContext | null) => boolean;
}

// 명령어 패턴 목록 (우선순위 순)
const COMMAND_PATTERNS: CommandPattern[] = [
  // 회의 시작/생성
  {
    keywords: ['회의', '미팅'],
    condition: (cmd) => {
      const lower = cmd.toLowerCase();
      return (
        lower.includes('시작') ||
        lower.includes('새') ||
        lower.includes('만들') ||
        lower.includes('미팅')
      );
    },
    response: 'meeting_create',
  },

  // 검색
  {
    keywords: ['검색', '찾'],
    response: 'search',
  },

  // Blame / 이력 (예산 이력보다 먼저 체크)
  {
    keywords: ['blame', '이력', '히스토리'],
    response: 'blame',
  },

  // 예산 (이력 제외)
  {
    keywords: ['예산'],
    excludeKeywords: ['이력'],
    response: 'budget',
  },

  // 일정
  {
    keywords: ['일정', '스케줄', '오늘'],
    response: 'schedule',
  },

  // 팀 현황
  {
    keywords: ['팀'],
    condition: (cmd) => {
      const lower = cmd.toLowerCase();
      return lower.includes('현황') || lower.includes('상태');
    },
    response: 'team_status',
  },

  // Action Items
  {
    keywords: ['action', '할 일', '액션'],
    response: 'action_items',
  },
];

// 컨텍스트 기반 명령어 처리
function matchContextCommand(
  command: string,
  context: SessionContext
): MockResponse | null {
  const lowerCommand = command.toLowerCase();

  // "확정해줘" - branchId 있을 때 merge
  if (
    (lowerCommand.includes('확정') || lowerCommand.includes('머지')) &&
    context.branchId
  ) {
    return {
      ...MOCK_RESPONSES.merge,
      message: `${context.target}을(를) ${context.proposedValue}으로 확정했습니다. 변경 이력이 기록되었습니다.`,
    };
  }

  // 금액 변경 의도 감지
  const amountMatch = command.match(/(\d+천만원|\d+억)/);
  if (amountMatch && context.target) {
    return {
      ...MOCK_RESPONSES.budget,
      fields: MOCK_RESPONSES.budget.fields?.map((f) =>
        f.id === 'amount' ? { ...f, value: amountMatch[1] } : f
      ),
    };
  }

  return null;
}

// 패턴 기반 명령어 매칭
function matchPatternCommand(command: string): MockResponse {
  const lowerCommand = command.toLowerCase();

  for (const pattern of COMMAND_PATTERNS) {
    // 키워드 체크
    const hasKeyword = pattern.keywords.some((k) => lowerCommand.includes(k));
    if (!hasKeyword) continue;

    // 제외 키워드 체크
    if (pattern.excludeKeywords) {
      const hasExcluded = pattern.excludeKeywords.some((k) =>
        lowerCommand.includes(k)
      );
      if (hasExcluded) continue;
    }

    // 추가 조건 체크
    if (pattern.condition && !pattern.condition(command)) {
      continue;
    }

    return MOCK_RESPONSES[pattern.response];
  }

  return MOCK_RESPONSES.default;
}

/**
 * 명령어 매칭 함수
 * @param command 사용자 입력 명령어
 * @param context 세션 컨텍스트 (선택)
 * @returns MockResponse
 */
export function matchCommand(
  command: string,
  context?: SessionContext | null
): MockResponse {
  // 1. 컨텍스트 기반 매칭 시도
  if (context) {
    const contextMatch = matchContextCommand(command, context);
    if (contextMatch) return contextMatch;
  }

  // 2. 패턴 기반 매칭
  return matchPatternCommand(command);
}
