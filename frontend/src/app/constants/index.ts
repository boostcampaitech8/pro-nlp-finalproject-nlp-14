// Spotlight 서비스 상수

// 히스토리 및 UI 상수
export const HISTORY_LIMIT = 50;
export const SUGGESTIONS_DISPLAY_LIMIT = 4;

// Status 색상 매핑
export const STATUS_COLORS = {
  success: 'bg-mit-success/20 text-mit-success',
  error: 'bg-mit-warning/20 text-mit-warning',
  pending: 'bg-mit-primary/20 text-mit-primary',
} as const;

export type StatusType = keyof typeof STATUS_COLORS;

// Preview 타이틀 매핑
export const PREVIEW_TITLES: Record<string, string> = {
  empty: 'Preview',
  meeting: 'Meeting Details',
  document: 'Document Preview',
  'search-result': 'Search Result',
  'command-result': 'Command Result',
};

// API 딜레이 (Mock)
export const API_DELAYS = {
  COMMAND_PROCESS: 500,
  FORM_SUBMIT: 800,
  SUGGESTIONS_FETCH: 200,
} as const;
