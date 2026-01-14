// 명령 관련 타입 정의

export type FieldType = 'text' | 'number' | 'select' | 'date' | 'textarea';

export interface CommandField {
  id: string;
  label: string;
  type: FieldType;
  value?: string;
  placeholder?: string;
  options?: string[];
  required?: boolean;
}

export interface ActiveCommand {
  id: string;
  type: string;
  title: string;
  description: string;
  fields: CommandField[];
  icon?: string;
}

export interface HistoryItem {
  id: string;
  command: string;
  result: string;
  timestamp: Date;
  icon: string;
  status: 'success' | 'error' | 'pending';
}

export interface Suggestion {
  id: string;
  title: string;
  description: string;
  icon: string;
  command: string;
  category: 'meeting' | 'search' | 'action' | 'help';
}

// Mock 데이터를 위한 에이전트 응답 타입
export interface AgentResponse {
  type: 'direct' | 'form';
  message?: string;
  command?: ActiveCommand;
  previewData?: {
    type: string;
    title: string;
    content: string;
  };
}
