// 에이전트 서비스 (Mock API)
// 실제 백엔드 API 연동 전까지 사용하는 Mock 데이터

import type { ActiveCommand, AgentResponse, SessionContext } from '@/app/types/command';
import { API_DELAYS } from '@/app/constants';
import { matchCommand } from './commandMatcher';

export const agentService = {
  /**
   * 명령어 처리
   * @param command 사용자가 입력한 명령어
   * @param context 세션 컨텍스트 (선택)
   * @returns AgentResponse
   */
  async processCommand(command: string, context?: SessionContext | null): Promise<AgentResponse> {
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.COMMAND_PROCESS));

    const matched = matchCommand(command, context);

    // 모달 타입 응답 처리
    if (matched.type === 'modal' && matched.modalData) {
      return {
        type: 'modal',
        tool: matched.tool,
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
        tool: matched.tool,
        command: activeCommand,
      };
    }

    // 직접 응답 처리
    return {
      type: 'direct',
      tool: matched.tool,
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
    // API 호출 시뮬레이션
    await new Promise((resolve) => setTimeout(resolve, API_DELAYS.FORM_SUBMIT));

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
