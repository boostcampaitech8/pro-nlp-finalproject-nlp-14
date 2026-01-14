// 명령 처리 훅
import { useCallback } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { usePreviewStore } from '@/app/stores/previewStore';
import type { AgentResponse, HistoryItem } from '@/app/types/command';

// Mock 에이전트 응답 생성
function getMockAgentResponse(command: string): AgentResponse {
  const lowerCommand = command.toLowerCase();

  // 회의 시작 명령
  if (lowerCommand.includes('회의') && (lowerCommand.includes('시작') || lowerCommand.includes('새'))) {
    return {
      type: 'form',
      command: {
        id: `cmd-${Date.now()}`,
        type: 'create-meeting',
        title: '새 회의 만들기',
        description: '회의 정보를 입력해주세요',
        icon: '🎯',
        fields: [
          {
            id: 'title',
            label: '회의 제목',
            type: 'text',
            placeholder: '예: 주간 팀 미팅',
            required: true,
          },
          {
            id: 'team',
            label: '팀 선택',
            type: 'select',
            options: ['개발팀', '디자인팀', '마케팅팀', '전체'],
            required: true,
          },
          {
            id: 'description',
            label: '설명',
            type: 'textarea',
            placeholder: '회의 안건이나 목적을 입력하세요',
          },
        ],
      },
    };
  }

  // 검색 명령
  if (lowerCommand.includes('검색') || lowerCommand.includes('찾')) {
    return {
      type: 'form',
      command: {
        id: `cmd-${Date.now()}`,
        type: 'search',
        title: '회의록 검색',
        description: '검색 조건을 입력해주세요',
        icon: '🔍',
        fields: [
          {
            id: 'keyword',
            label: '검색어',
            type: 'text',
            placeholder: '검색할 키워드',
            required: true,
          },
          {
            id: 'dateRange',
            label: '기간',
            type: 'select',
            options: ['최근 1주일', '최근 1개월', '최근 3개월', '전체'],
          },
        ],
      },
    };
  }

  // 일정 확인
  if (lowerCommand.includes('일정') || lowerCommand.includes('스케줄')) {
    return {
      type: 'direct',
      message: '오늘 예정된 회의가 2건 있습니다.',
      previewData: {
        type: 'meeting',
        title: '오늘의 일정',
        content: '1. 10:00 - 주간 팀 미팅\n2. 14:00 - 프로젝트 리뷰',
      },
    };
  }

  // 팀 현황
  if (lowerCommand.includes('팀') && lowerCommand.includes('현황')) {
    return {
      type: 'direct',
      message: '팀 현황을 불러왔습니다.',
      previewData: {
        type: 'document',
        title: '팀 현황',
        content: '총 멤버: 8명\n진행 중인 프로젝트: 3개\n이번 주 회의: 5회',
      },
    };
  }

  // 기본 응답
  return {
    type: 'direct',
    message: `"${command}" 명령을 처리했습니다.`,
    previewData: {
      type: 'command-result',
      title: '명령 결과',
      content: `입력: ${command}\n\n아직 이 명령에 대한 구체적인 처리가 구현되지 않았습니다.`,
    },
  };
}

export function useCommand() {
  const {
    inputValue,
    activeCommand,
    setInputValue,
    setProcessing,
    setActiveCommand,
    updateField,
    addHistory,
    clearActiveCommand,
  } = useCommandStore();

  const { setPreview } = usePreviewStore();

  // 명령 제출
  const submitCommand = useCallback(
    async (command?: string) => {
      const cmd = command || inputValue;
      if (!cmd.trim()) return;

      setProcessing(true);
      setInputValue('');

      // Mock API 호출 (실제로는 백엔드 API 호출)
      await new Promise((resolve) => setTimeout(resolve, 500));

      const response = getMockAgentResponse(cmd);

      if (response.type === 'form' && response.command) {
        // Form 표시
        setActiveCommand(response.command);
      } else {
        // 직접 결과 표시
        const historyItem: HistoryItem = {
          id: `history-${Date.now()}`,
          command: cmd,
          result: response.message || '완료',
          timestamp: new Date(),
          icon: '✅',
          status: 'success',
        };
        addHistory(historyItem);

        // 프리뷰 패널 업데이트
        if (response.previewData) {
          setPreview(response.previewData.type as 'meeting' | 'document' | 'command-result', {
            title: response.previewData.title,
            content: response.previewData.content,
            createdAt: new Date().toISOString(),
          });
        }
      }

      setProcessing(false);
    },
    [inputValue, setInputValue, setProcessing, setActiveCommand, addHistory, setPreview]
  );

  // Form 제출
  const submitForm = useCallback(async () => {
    if (!activeCommand) return;

    setProcessing(true);

    // Mock API 호출
    await new Promise((resolve) => setTimeout(resolve, 800));

    // 필드 값 추출
    const fieldValues = activeCommand.fields
      .map((f) => `${f.label}: ${f.value || '(미입력)'}`)
      .join('\n');

    const historyItem: HistoryItem = {
      id: `history-${Date.now()}`,
      command: activeCommand.title,
      result: `${activeCommand.title} 완료`,
      timestamp: new Date(),
      icon: activeCommand.icon || '✅',
      status: 'success',
    };
    addHistory(historyItem);

    // 프리뷰 업데이트
    setPreview('command-result', {
      title: `${activeCommand.title} 결과`,
      content: `명령이 성공적으로 실행되었습니다.\n\n${fieldValues}`,
      createdAt: new Date().toISOString(),
    });

    clearActiveCommand();
  }, [activeCommand, setProcessing, addHistory, setPreview, clearActiveCommand]);

  // 명령 취소
  const cancelCommand = useCallback(() => {
    clearActiveCommand();
  }, [clearActiveCommand]);

  return {
    inputValue,
    activeCommand,
    setInputValue,
    submitCommand,
    submitForm,
    cancelCommand,
    updateField,
  };
}
