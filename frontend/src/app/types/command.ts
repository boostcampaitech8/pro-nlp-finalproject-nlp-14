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

// HITL 필드 선택 옵션
export interface HITLFieldOption {
  value: string; // 실제 저장될 값 (예: UUID)
  label: string; // 사용자에게 보여줄 텍스트 (예: 팀 이름)
}

// HITL 필수 입력 필드 정의
export interface HITLRequiredField {
  name: string;
  description: string;
  type: string; // 'string' | 'uuid' | 'datetime' | 'number'
  required: boolean;
  // 확장 필드
  input_type?: 'text' | 'select' | 'multiselect' | 'checkbox' | 'datetime' | 'number' | 'textarea';
  options?: HITLFieldOption[]; // select/multiselect용 옵션
  placeholder?: string;
  // 기본값 (LLM이 추출한 값)
  default_value?: string | null;
  default_display?: string | null; // select용 표시 값 (UUID → 이름)
}

// HITL 확인 요청 데이터
export interface HITLData {
  tool_name: string;
  params: Record<string, unknown>;
  params_display?: Record<string, string>; // UUID → 이름 변환된 표시용 값
  message: string;
  required_fields?: HITLRequiredField[];
  display_template?: string; // 자연어 템플릿 ({{param}}이 input으로 대체됨)
}

// 채팅 메시지 타입
export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  type?: 'text' | 'plan' | 'hitl';
  content: string;
  timestamp: Date;
  approved?: boolean;
  // HITL 전용 필드
  hitlData?: HITLData;
  hitlStatus?: 'pending' | 'confirmed' | 'cancelled';
  hitlCancelReason?: 'user' | 'auto';
}

// 대기 메시지 타입
export type PendingMessage = {
  id: string;
  text: string;
};

// 에이전트 응답 타입 (text 또는 plan)
export interface AgentResponse {
  type: 'text' | 'plan';
  message: string;
}

// Plan 응답 파싱 세그먼트
export type PlanSegment =
  | { type: 'text'; value: string }
  | { type: 'field'; id: string; defaultValue: string };
