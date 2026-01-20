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

// 모달 데이터 타입
export interface ModalData {
  modalType: 'meeting';
  title?: string;
  description?: string;
  scheduledAt?: string;
  teamId?: string;
}

// Tool 타입 정의
export type MitTool = 'mit_blame' | 'mit_search' | 'mit_branch' | 'mit_merge';
export type UtilTool = 'mit_summary' | 'mit_action';
export type McpTool = 'mcp_jira' | 'mcp_notion' | 'mcp_slack' | 'mcp_calendar';
export type AgentTool = MitTool | UtilTool | McpTool;

// 세션 컨텍스트 (시나리오 흐름 유지용)
export interface SessionContext {
  target?: string;          // "프로젝트 X 예산"
  currentValue?: string;    // "5,000만원"
  branchId?: string;        // branch 생성 시 ID
  proposedValue?: string;   // "6,000만원"
}

// Mock 데이터를 위한 에이전트 응답 타입
export interface AgentResponse {
  type: 'direct' | 'form' | 'modal';
  message?: string;
  command?: ActiveCommand;
  modalData?: ModalData;
  previewData?: {
    type: string;
    title: string;
    content: string;
  };
  tool?: AgentTool;
  context?: SessionContext;
}
