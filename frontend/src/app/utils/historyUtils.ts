// 히스토리 관련 유틸리티
import type { HistoryItem, HistoryStatus } from '@/app/types/command';

// 히스토리 아이템 생성
export function createHistoryItem(
  command: string,
  result: string,
  options?: {
    icon?: string;
    status?: HistoryStatus;
  }
): HistoryItem {
  return {
    id: `history-${Date.now()}`,
    command,
    result,
    timestamp: new Date(),
    icon: options?.icon ?? '✅',
    status: options?.status ?? 'success',
  };
}

// 성공 히스토리 아이템 생성
export function createSuccessHistoryItem(
  command: string,
  result: string,
  icon?: string
): HistoryItem {
  return createHistoryItem(command, result, {
    icon: icon ?? '✅',
    status: 'success',
  });
}

// 에러 히스토리 아이템 생성
export function createErrorHistoryItem(
  command: string,
  result: string = '명령 처리 중 오류가 발생했습니다.'
): HistoryItem {
  return createHistoryItem(command, result, {
    icon: '❌',
    status: 'error',
  });
}
