# Spotlight Service 명세

## 개요

Spotlight Service는 Mit의 메인 인터페이스로, 사용자가 자연어 명령을 통해 시스템과 상호작용할 수 있는 통합 서비스입니다. macOS Spotlight나 VS Code Command Palette와 유사한 UX를 제공하며, 명령 입력, 대화형 폼 생성, 결과 미리보기를 하나의 흐름으로 통합합니다.

## 핵심 가치

| 가치 | 설명 |
|------|------|
| **통합 인터페이스** | 모든 작업을 하나의 입력창으로 처리 |
| **컨텍스트 유지** | 명령 히스토리와 결과를 우측 패널에서 지속적으로 참조 |
| **대화형 흐름** | 필요 시 폼을 동적으로 생성하여 추가 정보 수집 |
| **즉각적 피드백** | 명령 실행 결과를 실시간으로 미리보기 패널에 표시 |

---

## 아키텍처

### 3-Column 레이아웃

```
┌─────────────────────────────────────────────────────────────┐
│                     MainLayout                               │
├──────────┬──────────────────────────────────┬───────────────┤
│          │                                  │               │
│  Left    │        Center Content            │    Right      │
│ Sidebar  │      (SpotlightInput +           │   Preview     │
│          │       Suggestions +              │    Panel      │
│  280px   │        History)                  │    400px      │
│          │                                  │               │
│  - Nav   │  ┌────────────────────────┐     │  ┌─────────┐ │
│  - Team  │  │ CommandSuggestions     │     │  │ Header  │ │
│  - Menu  │  │   (빠른 명령)          │     │  ├─────────┤ │
│          │  └────────────────────────┘     │  │         │ │
│          │                                  │  │ Content │ │
│          │  ┌────────────────────────┐     │  │         │ │
│          │  │  SpotlightInput        │     │  │         │ │
│          │  │    + InteractiveForm   │     │  ├─────────┤ │
│          │  └────────────────────────┘     │  │  Meta   │ │
│          │                                  │  └─────────┘ │
│          │  ┌────────────────────────┐     │               │
│          │  │ CommandHistory         │     │               │
│          │  │   (최근 활동)          │     │               │
│          │  └────────────────────────┘     │               │
│          │                                  │               │
└──────────┴──────────────────────────────────┴───────────────┘
```

**레이아웃 규칙**
- 좌측 사이드바: 고정 280px (네비게이션, 팀 목록, 현재 세션)
- 중앙 콘텐츠: flex-1 (반응형, 최소 너비 확보)
- 우측 프리뷰: 고정 400px (결과 미리보기, 메타데이터)

---

## 컴포넌트 계층 구조

### 1. 페이지 레이어

```
MainLayout (layouts/MainLayout.tsx)
├─ LeftSidebar (components/sidebar/LeftSidebar.tsx)
├─ MainPage (pages/MainPage.tsx)
│  ├─ CommandSuggestions (components/spotlight/CommandSuggestions.tsx)
│  ├─ SpotlightInput (components/spotlight/SpotlightInput.tsx)
│  ├─ InteractiveForm (components/spotlight/InteractiveForm.tsx)
│  └─ CommandHistory (components/spotlight/CommandHistory.tsx)
└─ RightSidebar (components/preview/RightSidebar.tsx)
   ├─ PreviewHeader
   ├─ PreviewContent
   └─ PreviewMeta
```

### 2. Spotlight 입력 컴포넌트

**SpotlightInput.tsx**
- 역할: 메인 명령 입력창
- 기능:
  - 자연어 명령 입력
  - Cmd+K 단축키 (포커스)
  - Enter 제출, Shift+Enter 줄바꿈
  - 처리 중 상태 표시 (Loader 애니메이션)
- 상태:
  - `inputValue`: 현재 입력값
  - `isProcessing`: 명령 처리 중 여부
  - `isInputFocused`: 포커스 상태

```typescript
// 주요 기능
- Cmd+K 글로벌 단축키로 포커스
- 입력값은 commandStore에서 관리
- Enter 시 submitCommand() 호출
```

### 3. 추천 명령 컴포넌트

**CommandSuggestions.tsx**
- 역할: 빠른 실행을 위한 추천 명령 카드
- 데이터: `agentService.getSuggestions()`에서 로드
- 표시: 2-column 그리드 (최대 4개 제한)
- 카테고리: meeting, search, action, help

```typescript
interface Suggestion {
  id: string;
  title: string;
  description: string;
  icon: string;
  command: string;  // 클릭 시 실행할 명령
  category: 'meeting' | 'search' | 'action' | 'help';
}
```

### 4. 명령 히스토리 컴포넌트

**CommandHistory.tsx**
- 역할: 최근 실행한 명령 히스토리 표시
- 제한: 최대 50개 (HISTORY_LIMIT)
- 클릭 시: 우측 미리보기 패널에 결과 표시
- 상태 표시: success(완료), error(실패), pending(진행)

```typescript
interface HistoryItem {
  id: string;
  command: string;
  result: string;
  timestamp: Date;
  icon: string;
  status: 'success' | 'error' | 'pending';
}
```

### 5. 대화형 폼 컴포넌트

**InteractiveForm.tsx**
- 역할: 명령에 필요한 추가 정보를 동적으로 수집
- 트리거: `agentService`가 응답 타입 'form' 반환 시
- 애니메이션: Framer Motion으로 부드러운 등장/퇴장
- 필드 타입:
  - `text`: 텍스트 입력
  - `textarea`: 여러 줄 입력
  - `select`: 드롭다운 선택
  - `date`: 날짜 선택
  - `number`: 숫자 입력

```typescript
interface CommandField {
  id: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'date' | 'textarea';
  value?: string;
  placeholder?: string;
  options?: string[];  // select 타입 전용
  required?: boolean;
}

interface ActiveCommand {
  id: string;
  type: string;
  title: string;
  description: string;
  fields: CommandField[];
  icon?: string;
}
```

**폼 생성 예시**
```typescript
// "회의록 검색" 명령 시
{
  title: '회의록 검색',
  description: '검색 조건을 입력해주세요',
  icon: '🔍',
  fields: [
    { id: 'keyword', label: '검색어', type: 'text', required: true },
    { id: 'dateRange', label: '검색 기간', type: 'select',
      options: ['최근 1주일', '최근 1개월', '최근 3개월', '전체 기간'] },
    { id: 'team', label: '팀 필터', type: 'select',
      options: ['전체', '개발팀', '디자인팀', '마케팅팀'] }
  ]
}
```

---

## 명령 실행 흐름

### 전체 파이프라인

```
[사용자 입력]
     |
     v
[SpotlightInput] ──> submitCommand()
     |
     v
[agentService.processCommand()] ──> 키워드 매칭
     |
     +──────────────┬──────────────┬──────────────+
     v              v              v              v
  'direct'       'form'        'modal'      (에러)
     |              |              |              |
     v              v              v              v
히스토리 추가   폼 표시    모달 오픈    에러 히스토리
     |              |
     v              v
미리보기 업데이트   [사용자 폼 작성]
                    |
                    v
               submitForm()
                    |
                    v
            agentService.submitForm()
                    |
                    v
               히스토리 추가
                    |
                    v
            미리보기 업데이트
```

### 1. 명령 입력 단계

```typescript
// useCommand.ts - submitCommand()
const submitCommand = async (command?: string) => {
  const cmd = command || inputValue;
  if (!cmd.trim()) return;

  setProcessing(true);
  setInputValue('');

  try {
    // agentService를 통해 명령 처리
    const response = await agentService.processCommand(cmd);

    // 응답 타입에 따른 분기 처리
    if (response.type === 'modal') {
      // 모달 오픈 (예: 회의 생성)
      openMeetingModal(response.modalData);
    } else if (response.type === 'form') {
      // 대화형 폼 표시
      setActiveCommand(response.command);
    } else {
      // 직접 결과 표시
      addHistory({...});
      setPreview(response.previewData);
    }
  } catch (error) {
    addHistory({ status: 'error', ... });
  } finally {
    setProcessing(false);
  }
};
```

### 2. AgentService 처리 단계

**키워드 기반 명령 매칭**

```typescript
// agentService.ts - matchCommand()
function matchCommand(command: string): MockResponse {
  const lowerCommand = command.toLowerCase();

  // 회의 시작/생성
  if (lowerCommand.includes('회의') &&
      (lowerCommand.includes('시작') || lowerCommand.includes('만들'))) {
    return { type: 'modal', modalData: { modalType: 'meeting' } };
  }

  // 검색
  if (lowerCommand.includes('검색') || lowerCommand.includes('찾')) {
    return { type: 'form', fields: [...] };
  }

  // Blame / 이력
  if (lowerCommand.includes('blame') || lowerCommand.includes('이력')) {
    return { type: 'direct', message: '...', previewContent: '...' };
  }

  // 기본 응답
  return { type: 'form', fields: [...] };
}
```

**응답 타입별 처리**

| 타입 | 설명 | 반환 데이터 |
|------|------|-----------|
| `direct` | 즉시 결과 표시 | `message`, `previewData` |
| `form` | 추가 정보 필요 | `command` (ActiveCommand) |
| `modal` | 모달 UI 필요 | `modalData` (ModalData) |

### 3. 폼 제출 단계

```typescript
// useCommand.ts - submitForm()
const submitForm = async () => {
  if (!activeCommand) return;

  setProcessing(true);

  try {
    // 필드 값 추출
    const fieldValues: Record<string, string> = {};
    activeCommand.fields.forEach((f) => {
      if (f.value) fieldValues[f.id] = f.value;
    });

    // agentService를 통해 Form 제출
    const response = await agentService.submitForm(
      activeCommand.id,
      activeCommand.title,
      fieldValues
    );

    // 히스토리 추가 및 미리보기 업데이트
    addHistory({...});
    setPreview('command-result', response.previewData);

    clearActiveCommand();
  } catch (error) {
    addHistory({ status: 'error', ... });
  }
};
```

---

## 상태 관리 (Zustand Stores)

### 1. CommandStore (stores/commandStore.ts)

**역할**: 명령 입력, 히스토리, 활성 폼 관리

```typescript
interface CommandState {
  // 상태
  inputValue: string;              // 현재 입력값
  isInputFocused: boolean;         // 포커스 상태
  isProcessing: boolean;           // 명령 처리 중
  activeCommand: ActiveCommand | null;  // 활성 폼
  history: HistoryItem[];          // 명령 히스토리 (최대 50개)
  suggestions: Suggestion[];       // 추천 명령

  // Actions
  setInputValue: (value: string) => void;
  setInputFocused: (focused: boolean) => void;
  setProcessing: (processing: boolean) => void;
  setActiveCommand: (command: ActiveCommand | null) => void;
  updateField: (fieldId: string, value: string) => void;  // 폼 필드 업데이트
  addHistory: (item: HistoryItem) => void;
  clearHistory: () => void;
  clearActiveCommand: () => void;
  setSuggestions: (suggestions: Suggestion[]) => void;
}
```

**히스토리 관리**
- 최대 50개 제한 (HISTORY_LIMIT)
- 최신 항목이 상단에 표시
- 각 항목은 상태(success/error/pending)와 타임스탬프 포함

### 2. PreviewStore (stores/previewStore.ts)

**역할**: 우측 미리보기 패널 상태 관리

```typescript
interface PreviewState {
  previewType: PreviewType;        // 현재 미리보기 타입
  previewData: PreviewData | null; // 미리보기 데이터
  isLoading: boolean;              // 로딩 상태

  // Actions
  setPreview: (type: PreviewType, data: PreviewData | null) => void;
  clearPreview: () => void;
  setLoading: (loading: boolean) => void;
}

type PreviewType = 'empty' | 'meeting' | 'document' | 'search-result' | 'command-result';

interface PreviewData {
  id?: string;
  title?: string;
  description?: string;
  content?: string;              // Markdown 지원
  metadata?: Record<string, unknown>;
  createdAt?: string;
  updatedAt?: string;
}
```

**미리보기 타입별 용도**

| 타입 | 사용 케이스 |
|------|-----------|
| `empty` | 초기 상태, 아무것도 선택되지 않음 |
| `meeting` | 회의 정보 표시 |
| `document` | 문서 내용 표시 |
| `search-result` | 검색 결과 표시 |
| `command-result` | 명령 실행 결과 표시 |

### 3. MeetingModalStore (stores/meetingModalStore.ts)

**역할**: 회의 생성 모달 상태 관리

```typescript
interface MeetingModalState {
  isOpen: boolean;
  initialData: MeetingModalData | null;

  openModal: (data?: MeetingModalData) => void;
  closeModal: () => void;
}

interface MeetingModalData {
  title?: string;
  description?: string;
  scheduledAt?: string;
  teamId?: string;
}
```

---

## 훅 (Hooks)

### useCommand (hooks/useCommand.ts)

**역할**: 명령 실행 로직을 캡슐화한 커스텀 훅

```typescript
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
  const { openModal: openMeetingModal } = useMeetingModalStore();

  return {
    inputValue,
    activeCommand,
    setInputValue,
    submitCommand,    // 명령 제출
    submitForm,       // 폼 제출
    cancelCommand,    // 명령 취소
    updateField,      // 폼 필드 업데이트
  };
}
```

**사용 예시**
```typescript
function SpotlightInput() {
  const { inputValue, setInputValue, submitCommand } = useCommand();

  const handleSubmit = () => {
    if (!inputValue.trim()) return;
    submitCommand();
  };

  return (
    <input
      value={inputValue}
      onChange={(e) => setInputValue(e.target.value)}
      onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
    />
  );
}
```

---

## AgentService (Mock 구현)

### 현재 구현 (services/agentService.ts)

**목적**: 백엔드 API 연동 전까지 사용하는 Mock 서비스

```typescript
export const agentService = {
  /**
   * 명령어 처리
   * @param command 사용자가 입력한 명령어
   * @returns AgentResponse
   */
  async processCommand(command: string): Promise<AgentResponse> {
    // API 호출 시뮬레이션 (500ms 딜레이)
    await new Promise((resolve) => setTimeout(resolve, 500));

    const matched = matchCommand(command);

    if (matched.type === 'modal') {
      return { type: 'modal', modalData: matched.modalData };
    }

    if (matched.type === 'form') {
      return { type: 'form', command: {...} };
    }

    return { type: 'direct', message: '...', previewData: {...} };
  },

  /**
   * Form 제출 처리
   */
  async submitForm(
    commandId: string,
    commandTitle: string,
    fields: Record<string, string>
  ): Promise<AgentResponse> {
    // API 호출 시뮬레이션 (800ms 딜레이)
    await new Promise((resolve) => setTimeout(resolve, 800));

    return {
      type: 'direct',
      message: `${commandTitle}이(가) 성공적으로 실행되었습니다.`,
      previewData: {...}
    };
  },

  /**
   * 추천 명령어 조회
   */
  async getSuggestions() {
    // API 호출 시뮬레이션 (200ms 딜레이)
    await new Promise((resolve) => setTimeout(resolve, 200));

    return [
      { id: '1', title: '새 회의 시작', command: '새 회의 시작', ... },
      { id: '2', title: '지난 회의록 검색', command: '회의록 검색', ... },
      { id: '3', title: '오늘 일정 확인', command: '오늘 일정', ... },
      { id: '4', title: '팀 현황 보기', command: '팀 현황', ... },
    ];
  },
};
```

### 키워드 매칭 규칙

| 키워드 조합 | 매칭 결과 | 응답 타입 |
|-----------|---------|---------|
| "회의" + ("시작" \| "새" \| "만들") | 회의 생성 | modal |
| "검색" \| "찾" | 회의록 검색 | form |
| "예산" (이력 제외) | 예산 변경 제안 | form |
| "blame" \| "이력" \| "히스토리" | Blame 조회 | direct |
| "일정" \| "스케줄" \| "오늘" | 일정 조회 | direct |
| "팀" + ("현황" \| "상태") | 팀 현황 | direct |

### 백엔드 연동 전환 계획

```typescript
// TODO: 백엔드 API 연동 시 교체
export const agentService = {
  async processCommand(command: string): Promise<AgentResponse> {
    // POST /api/v1/agent/command
    const response = await fetch('/api/v1/agent/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    return response.json();
  },

  async submitForm(commandId: string, commandTitle: string, fields: Record<string, string>) {
    // POST /api/v1/agent/form-submit
    const response = await fetch('/api/v1/agent/form-submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commandId, commandTitle, fields }),
    });
    return response.json();
  },

  async getSuggestions() {
    // GET /api/v1/agent/suggestions
    const response = await fetch('/api/v1/agent/suggestions');
    return response.json();
  },
};
```

---

## 상수 정의 (constants/index.ts)

```typescript
// 히스토리 및 UI 상수
export const HISTORY_LIMIT = 50;
export const SUGGESTIONS_DISPLAY_LIMIT = 4;

// Status 색상 매핑
export const STATUS_COLORS = {
  success: 'bg-mit-success/20 text-mit-success',
  error: 'bg-mit-warning/20 text-mit-warning',
  pending: 'bg-mit-primary/20 text-mit-primary',
} as const;

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
```

---

## 유틸리티 (utils/dateUtils.ts)

```typescript
/**
 * 상대 시간 포맷팅
 * 예: "방금 전", "3분 전", "2시간 전", "어제", "2일 전"
 */
export function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return '방금 전';
  if (diffMin < 60) return `${diffMin}분 전`;
  if (diffHour < 24) return `${diffHour}시간 전`;
  if (diffDay === 1) return '어제';
  if (diffDay < 7) return `${diffDay}일 전`;

  return date.toLocaleDateString('ko-KR', {
    month: 'short',
    day: 'numeric',
  });
}

/**
 * 기간 포맷팅
 * 예: "1분 30초", "2시간 15분"
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) return `${hours}시간 ${minutes}분`;
  if (minutes > 0) return `${minutes}분 ${secs}초`;
  return `${secs}초`;
}
```

---

## UI/UX 세부사항

### 1. 스타일링 (Tailwind CSS)

**Glass 효과**
```css
.glass-input {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
}

.glass-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.glass-card-hover:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.2);
}
```

**아이콘 컨테이너**
```css
.icon-container {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-container-sm {
  width: 32px;
  height: 32px;
}
```

**단축키 힌트**
```css
.shortcut-key {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
```

### 2. 애니메이션 (Framer Motion)

**InteractiveForm 등장/퇴장**
```typescript
<motion.div
  initial={{ opacity: 0, y: -20, height: 0 }}
  animate={{ opacity: 1, y: 0, height: 'auto' }}
  exit={{ opacity: 0, y: -20, height: 0 }}
  transition={{ duration: 0.2, ease: 'easeOut' }}
>
  <InteractiveForm />
</motion.div>
```

**CommandCard hover 효과**
```typescript
<button className="glass-card-hover transition-all duration-200">
  // 호버 시 배경색 변화, 테두리 밝아짐
</button>
```

### 3. 키보드 단축키

| 단축키 | 동작 |
|--------|------|
| `Cmd+K` (Mac) / `Ctrl+K` (Win) | SpotlightInput 포커스 |
| `Enter` | 명령 제출 / 폼 제출 |
| `Shift+Enter` | 줄바꿈 (textarea) |
| `Esc` | 폼 취소 (계획) |

---

## 확장 계획

### 1. 자동완성 (Autocomplete)

**계획**
- 입력 중 실시간 명령어 추천
- 과거 히스토리 기반 자동완성
- 팀 멤버, 회의, Agenda 이름 자동완성

```typescript
// 계획된 구현
interface AutocompleteItem {
  id: string;
  type: 'command' | 'meeting' | 'agenda' | 'member';
  text: string;
  icon?: string;
  score: number;  // 관련도 점수
}

// inputValue 변경 시 debounce로 자동완성 조회
useEffect(() => {
  const timer = setTimeout(() => {
    if (inputValue.length >= 2) {
      agentService.getAutocomplete(inputValue).then(setAutocompleteItems);
    }
  }, 300);
  return () => clearTimeout(timer);
}, [inputValue]);
```

### 2. 음성 입력 (Voice Input)

**계획**
- SpotlightInput의 마이크 버튼 활성화
- Web Speech API (브라우저 STT)
- 음성 -> 텍스트 변환 후 명령 실행

```typescript
// 계획된 구현
const startVoiceInput = () => {
  const recognition = new webkitSpeechRecognition();
  recognition.lang = 'ko-KR';
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    setInputValue(transcript);
    submitCommand(transcript);
  };
  recognition.start();
};
```

### 3. 명령 체이닝 (Command Chaining)

**계획**
- 여러 명령을 파이프라인으로 연결
- 예: "회의록 검색 -> Notion 저장 -> Slack 공유"

```typescript
// 계획된 구현
interface ChainedCommand {
  commands: Array<{
    action: string;
    params: Record<string, any>;
  }>;
}

// 예시: "지난주 예산 회의 검색해서 Drive에 저장하고 팀 채널에 공유해줘"
{
  commands: [
    { action: 'mit_search', params: { query: '지난주 예산 회의' } },
    { action: 'mcp_drive', params: { action: 'upload' } },
    { action: 'mcp_slack', params: { channel: '#team' } },
  ]
}
```

### 4. 템플릿 명령 (Command Templates)

**계획**
- 자주 사용하는 명령을 템플릿으로 저장
- 파라미터만 채워서 빠르게 실행

```typescript
interface CommandTemplate {
  id: string;
  name: string;
  description: string;
  command: string;
  params: Array<{
    key: string;
    label: string;
    type: FieldType;
  }>;
}

// 예시: "주간 회의 생성" 템플릿
{
  name: '주간 회의 생성',
  command: 'create_weekly_meeting',
  params: [
    { key: 'week', label: '주차', type: 'number' },
    { key: 'date', label: '날짜', type: 'date' },
  ]
}
```

---

## 성능 최적화

### 1. 히스토리 가상화 (Virtual Scrolling)

**현재**: 전체 히스토리 렌더링 (최대 50개)
**계획**: react-virtual로 가시 영역만 렌더링

### 2. 디바운싱 (Debouncing)

**적용 영역**
- 자동완성 조회 (300ms)
- 폼 필드 유효성 검사 (200ms)

### 3. 메모이제이션 (Memoization)

```typescript
// CommandHistory 컴포넌트
const CommandHistory = memo(() => {
  const { history } = useCommandStore();

  const sortedHistory = useMemo(() => {
    return [...history].sort((a, b) =>
      b.timestamp.getTime() - a.timestamp.getTime()
    );
  }, [history]);

  return (
    <div>
      {sortedHistory.map((item) => (
        <CommandCard key={item.id} item={item} />
      ))}
    </div>
  );
});
```

---

## 테스트 전략

### 1. 단위 테스트 (Unit Tests)

**대상**
- agentService 키워드 매칭 로직
- dateUtils 유틸리티 함수
- Zustand store actions

```typescript
// agentService.test.ts
describe('agentService.matchCommand', () => {
  it('회의 생성 키워드 매칭', () => {
    const result = matchCommand('새 회의 시작');
    expect(result.type).toBe('modal');
    expect(result.modalData?.modalType).toBe('meeting');
  });

  it('검색 키워드 매칭', () => {
    const result = matchCommand('회의록 검색');
    expect(result.type).toBe('form');
    expect(result.fields).toBeDefined();
  });
});
```

### 2. 통합 테스트 (Integration Tests)

**시나리오**
1. 명령 입력 -> 폼 생성 -> 폼 제출 -> 히스토리 추가 -> 미리보기 업데이트
2. 추천 명령 클릭 -> 즉시 실행 -> 결과 표시

### 3. E2E 테스트 (End-to-End Tests)

**Playwright 시나리오**
```typescript
test('Spotlight 명령 실행 흐름', async ({ page }) => {
  await page.goto('/');

  // 1. Cmd+K로 포커스
  await page.keyboard.press('Meta+K');

  // 2. 명령 입력
  await page.fill('input[placeholder*="Mit에게"]', '회의록 검색');
  await page.press('input[placeholder*="Mit에게"]', 'Enter');

  // 3. 폼 표시 확인
  await expect(page.locator('text=회의록 검색')).toBeVisible();

  // 4. 폼 작성
  await page.fill('input[placeholder*="검색어"]', 'Q1 회고');
  await page.selectOption('select', '최근 1개월');

  // 5. 실행
  await page.click('button:has-text("실행")');

  // 6. 히스토리 추가 확인
  await expect(page.locator('text=회의록 검색').first()).toBeVisible();

  // 7. 미리보기 패널 업데이트 확인
  await expect(page.locator('[role="complementary"]')).toContainText('회의록 검색 결과');
});
```

---

## 트러블슈팅

### 1. 폼 애니메이션 깜빡임

**문제**: InteractiveForm이 등장/퇴장 시 깜빡이는 현상
**원인**: AnimatePresence의 mode 설정 오류
**해결**: `mode="wait"` 설정으로 퇴장 완료 후 등장

```typescript
<AnimatePresence mode="wait">
  {activeCommand && <InteractiveForm command={activeCommand} />}
</AnimatePresence>
```

### 2. 히스토리 중복 추가

**문제**: 동일 명령이 히스토리에 중복 추가
**원인**: submitCommand와 submitForm에서 각각 addHistory 호출
**해결**: submitForm에서만 히스토리 추가 (submitCommand는 form 타입 시 skip)

### 3. 프리뷰 타입 불일치 에러

**문제**: `Unknown preview type: xxx` 경고 발생
**원인**: agentService가 반환한 previewType이 PreviewType enum에 없음
**해결**: 유효성 검사 후 fallback

```typescript
const previewType = response.previewData.type;
if (isValidPreviewType(previewType)) {
  setPreview(previewType, response.previewData);
} else {
  console.warn(`Unknown preview type: ${previewType}, falling back to command-result`);
  setPreview('command-result', response.previewData);
}
```

---

## 참조

- 타입 정의: [app/types/command.ts](../../../frontend/src/app/types/command.ts)
- Agent 서비스: [app/services/agentService.ts](../../../frontend/src/app/services/agentService.ts)
- 명령 스토어: [app/stores/commandStore.ts](../../../frontend/src/app/stores/commandStore.ts)
- 미리보기 스토어: [app/stores/previewStore.ts](../../../frontend/src/app/stores/previewStore.ts)
- 메인 레이아웃: [app/layouts/MainLayout.tsx](../../../frontend/src/app/layouts/MainLayout.tsx)
- 개요 문서: [00-overview.md](../00-overview.md)
- 유즈케이스: [usecase/01-usecase-specs.md](../usecase/01-usecase-specs.md)
