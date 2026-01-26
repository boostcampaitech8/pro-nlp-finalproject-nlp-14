# 채팅 시스템 (Chat System)

## 개요

Mit의 채팅 시스템은 **실시간 회의 중 텍스트 커뮤니케이션**을 지원하는 기능이다. 음성 회의를 보조하여 링크 공유, 코드 스니펫, 보충 설명 등을 텍스트로 전달할 수 있다.

### 목적

- 음성으로 전달하기 어려운 정보(URL, 코드, 수식 등)를 텍스트로 공유
- 회의 중 발언 기회를 기다리지 않고 빠른 텍스트 코멘트 제공
- 발화 기록(Transcript)과 별도로 명시적인 텍스트 기록 보존
- Markdown 지원을 통한 풍부한 텍스트 표현

### 핵심 특징

| 특징 | 설명 |
|------|------|
| **실시간 전송** | LiveKit DataPacket을 통한 실시간 메시지 전송 |
| **DB 영구 저장** | 서버가 DataPacket을 수신하여 PostgreSQL에 저장 |
| **Markdown 지원** | 코드 블록, 링크, 강조 등 Markdown 렌더링 |
| **연속 메시지 그룹화** | 같은 사용자의 1분 이내 메시지를 시각적으로 그룹화 |
| **히스토리 조회** | 회의 참여 시 과거 채팅 메시지 자동 로드 |

---

## 아키텍처

### 전체 데이터 흐름

```
[사용자 입력]
     |
     v
+--------------------+
|   ChatPanel        |
|   (Frontend)       |
+--------------------+
     |
     | onSendMessage()
     v
+--------------------+
|   useLiveKit       |
|   sendChatMessage()|
+--------------------+
     |
     | LiveKit DataPacket (WebSocket)
     v
+--------------------+
|   LiveKit SFU      |
+--------------------+
     |
     | Data broadcast
     +-----------------+-----------------+
     |                 |                 |
     v                 v                 v
[Participant A]   [Participant B]   [Backend Webhook]
     |                 |                 |
     |                 |                 v
     |                 |          +------------------+
     |                 |          | livekit_webhooks |
     |                 |          +------------------+
     |                 |                 |
     |                 |                 v
     |                 |          +------------------+
     |                 |          |  ChatService     |
     |                 |          |  (DB 저장)       |
     |                 |          +------------------+
     |                 |                 |
     |                 |                 v
     |                 |          +------------------+
     |                 |          |   PostgreSQL     |
     |                 |          +------------------+
     |                 |
     +--------+--------+
              |
              v
     (로컬 스토어 추가)
```

### 채팅 히스토리 조회 흐름

```
[회의 참여 시]
     |
     v
+--------------------+
|   useLiveKit       |
|   joinRoom()       |
+--------------------+
     |
     | fetchChatHistory()
     v
+--------------------+
|  GET /meetings/    |
|  {id}/chat         |
+--------------------+
     |
     v
+--------------------+
|  ChatService       |
|  get_messages()    |
+--------------------+
     |
     v
+--------------------+
|   PostgreSQL       |
+--------------------+
     |
     v
+--------------------+
|  meetingRoomStore  |
|  setChatMessages() |
+--------------------+
     |
     v
+--------------------+
|   ChatPanel        |
|   (렌더링)          |
+--------------------+
```

---

## 백엔드 구성

### 데이터 모델

**파일**: `/backend/app/models/chat.py`

```python
class ChatMessage(Base):
    """채팅 메시지 모델"""

    id: UUID                  # 메시지 고유 ID
    meeting_id: UUID          # 회의 ID (FK, CASCADE DELETE)
    user_id: UUID             # 발신자 ID (FK)
    content: Text             # 메시지 내용 (Markdown)
    created_at: DateTime      # 생성 시각 (UTC)

    # Relationships
    meeting                   # Meeting 엔티티 참조
    user                      # User 엔티티 참조
```

**특징**:
- `meeting_id`에 CASCADE DELETE 설정: 회의 삭제 시 채팅도 자동 삭제
- `created_at` 인덱스: 시간순 정렬 성능 최적화
- `content`는 TEXT 타입: 긴 메시지 지원

### 서비스 계층

**파일**: `/backend/app/services/chat_service.py`

```python
class ChatService:
    """채팅 메시지 CRUD 서비스"""

    async def create_message(meeting_id, user_id, content) -> ChatMessage
        # 메시지 생성 (공백 검증 포함)

    async def get_messages(meeting_id, page, limit) -> list[ChatMessage]
        # 페이지네이션 지원 메시지 조회 (최신순 DESC)

    async def get_message_count(meeting_id) -> int
        # 회의의 총 메시지 개수
```

**핵심 로직**:
1. **create_message**: 빈 메시지 방지 (strip 후 검증)
2. **get_messages**:
   - 최신순 DESC 정렬 (DB 쿼리)
   - User eager loading (N+1 방지)
   - 페이지네이션 (기본 50개)

### API 엔드포인트

**파일**: `/backend/app/api/v1/endpoints/chat.py`

#### GET /meetings/{meeting_id}/chat

**용도**: 회의 채팅 히스토리 조회

**요청**:
```
GET /api/v1/meetings/{meeting_id}/chat?page=1&limit=100
Authorization: Bearer <token>
```

**응답**:
```json
{
  "messages": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "meeting_id": "123e4567-e89b-12d3-a456-426614174000",
      "user_id": "789e0123-e45b-67c8-d901-234567890abc",
      "user_name": "김철수",
      "content": "# 프로젝트 일정\n\n- 1단계: 2026-02-01\n- 2단계: 2026-03-01",
      "created_at": "2026-01-27T10:30:45.123456+00:00"
    }
  ],
  "total": 45,
  "page": 1,
  "limit": 100
}
```

**권한**: `require_meeting_participant` 의존성 - 회의 참여자만 조회 가능

**정렬**:
- DB 쿼리: 최신순 DESC (페이지네이션용)
- API 응답: 엔드포인트에서 reverse() 처리하여 오래된 것 먼저 반환

### WebHook 통합 (미래 확장)

현재 채팅 메시지는 **클라이언트가 직접 DataPacket을 받아 로컬 스토어에 추가**하는 방식이다.

**미래 개선안**: LiveKit Webhook에서 DataPacket 수신
```python
# livekit_webhooks.py (미구현)
async def handle_data_received(body: dict, db: AsyncSession):
    """DataPacket 수신 이벤트 처리"""
    data_packet = body.get("dataPacket", {})
    if data_packet.get("type") == "chat_message":
        await chat_service.create_message(...)
```

---

## 프론트엔드 구성

### 타입 정의

**파일**: `/frontend/src/types/chat.ts`

```typescript
interface ChatMessage {
  id: string;           // UUID
  userId: string;       // 발신자 ID
  userName: string;     // 발신자 이름
  content: string;      // 메시지 내용 (Markdown)
  createdAt: string;    // ISO 8601 timestamp
}
```

### 상태 관리

**파일**: `/frontend/src/stores/meetingRoomStore.ts`

```typescript
interface MeetingRoomState {
  chatMessages: ChatMessage[];

  // Actions
  addChatMessage: (message: ChatMessage) => void;
  setChatMessages: (messages: ChatMessage[]) => void;
  clearChatMessages: () => void;
}
```

**특징**:
- 회의 단위 상태 격리 (회의 종료 시 `reset()` 호출로 초기화)
- 낙관적 업데이트: 자신의 메시지는 전송 즉시 로컬에 추가

### LiveKit 통합

**파일**: `/frontend/src/hooks/useLiveKit.ts`

#### 1. DataPacket 메시지 타입 정의

```typescript
interface DataMessage {
  type: 'vad_event' | 'chat_message' | 'force_mute' | 'mute_state';
  payload: unknown;
}

interface ChatMessagePayload {
  id: string;
  content: string;
  userName: string;
  createdAt: string;
}
```

#### 2. 채팅 메시지 전송

```typescript
const sendChatMessage = useCallback((content: string) => {
  const room = roomRef.current;
  if (!room) return;

  const messageId = crypto.randomUUID();
  const userName = room.localParticipant.name || room.localParticipant.identity;
  const createdAt = new Date().toISOString();

  // DataPacket으로 전송 (reliable=true)
  sendDataPacket({
    type: 'chat_message',
    payload: {
      id: messageId,
      content,
      userName,
      createdAt,
    } as ChatMessagePayload,
  });

  // 로컬에도 추가 (낙관적 업데이트)
  addChatMessage({
    id: messageId,
    userId: currentUserIdRef.current,
    userName,
    content,
    createdAt,
  });
}, [sendDataPacket, addChatMessage]);
```

**핵심**:
- `reliable: true` 옵션으로 전송 보장
- 낙관적 업데이트로 즉시 UI 반영

#### 3. DataPacket 수신 처리

```typescript
const handleDataReceived = useCallback(
  (payload: Uint8Array, participant?: RemoteParticipant) => {
    const decoder = new TextDecoder();
    const message: DataMessage = JSON.parse(decoder.decode(payload));

    switch (message.type) {
      case 'chat_message': {
        const chatPayload = message.payload as ChatMessagePayload;
        if (participant) {
          addChatMessage({
            id: chatPayload.id,
            userId: participant.identity,
            userName: chatPayload.userName || participant.name,
            content: chatPayload.content,
            createdAt: chatPayload.createdAt,
          });
        }
        break;
      }
      // ... 다른 타입 처리
    }
  },
  [addChatMessage]
);

// Room 이벤트 리스너 등록
room.on(RoomEvent.DataReceived, handleDataReceived);
```

#### 4. 채팅 히스토리 로드

```typescript
const fetchChatHistory = useCallback(async () => {
  try {
    const response = await api.get(`/meetings/${meetingId}/chat`);
    const messages = response.data.messages.map(msg => ({
      id: msg.id,
      userId: msg.user_id,
      userName: msg.user_name,
      content: msg.content,
      createdAt: msg.created_at,
    }));

    setChatMessages(messages);
    logger.log('[useLiveKit] Chat history loaded:', messages.length);
  } catch (err) {
    logger.warn('[useLiveKit] Failed to fetch chat history:', err);
  }
}, [meetingId, setChatMessages]);
```

**호출 시점**: `joinRoom()` 내부에서 토큰 획득과 병렬 처리
```typescript
const [tokenResponse] = await Promise.all([
  getJoinToken(),
  fetchChatHistory()
]);
```

### ChatPanel 컴포넌트

**파일**: `/frontend/src/components/meeting/ChatPanel.tsx`

#### Props 인터페이스

```typescript
interface ChatPanelProps {
  messages: ChatMessage[];              // 메시지 목록
  onSendMessage: (content: string) => void;  // 전송 핸들러
  disabled?: boolean;                   // 입력 비활성화
  currentUserId?: string;               // 현재 사용자 ID (자신 메시지 구분)
  hideHeader?: boolean;                 // 헤더 숨김 여부
}
```

#### 주요 기능

##### 1. 연속 메시지 그룹화

```typescript
const isContinuousMessage = (index: number): boolean => {
  if (index === 0) return false;

  const currentMsg = messages[index];
  const prevMsg = messages[index - 1];

  // 같은 사용자가 아니면 false
  if (currentMsg.userId !== prevMsg.userId) return false;

  // 시간 차이가 1분(60000ms) 미만이면 true
  const currentTime = new Date(currentMsg.createdAt).getTime();
  const prevTime = new Date(prevMsg.createdAt).getTime();
  return currentTime - prevTime < 60000;
};
```

**UI 반영**:
- 연속 메시지: 사용자명/시간 헤더 생략, 상단 마진 축소 (`mt-0.5`)
- 비연속 메시지: 사용자명/시간 표시, 정상 마진 (`mt-3`)

##### 2. Markdown 렌더링

```typescript
<MarkdownRenderer
  content={message.content}
  className={`prose-p:my-0 prose-headings:my-1 ${
    isOwn ? 'prose-invert' : 'prose-invert'
  }`}
/>
```

**지원 문법**:
- 헤딩, 리스트, 링크, 볼드/이탤릭
- 인라인 코드: `` `code` ``
- 코드 블록: ` ```language ... ``` `
- 구현체: `react-markdown` + `remark-gfm`

##### 3. 입력 UX

**키보드 단축키**:
- `Enter`: 메시지 전송
- `Shift + Enter`: 줄바꿈
- 한글 IME 조합 중: Enter 무시

```typescript
const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
  // 한글 IME 조합 중에는 Enter 처리하지 않음
  if (e.nativeEvent.isComposing) return;

  // Enter만 누르면 전송, Shift+Enter는 줄바꿈
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const trimmedValue = inputValue.trim();
    if (!trimmedValue) return;

    onSendMessage(trimmedValue);
    setInputValue('');
  }
};
```

**자동 높이 조절**:
```typescript
<textarea
  onInput={(e) => {
    const target = e.target as HTMLTextAreaElement;
    target.style.height = 'auto';
    target.style.height = Math.min(target.scrollHeight, 120) + 'px';
  }}
  className="resize-none min-h-[40px] max-h-[120px]"
/>
```

##### 4. 자동 스크롤

```typescript
useEffect(() => {
  if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
    messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }
}, [messages]);
```

**구현**:
- 메시지 목록 끝에 더미 `<div ref={messagesEndRef} />` 배치
- `messages` 배열 변경 시 자동 스크롤

##### 5. 시각적 구분

**자신의 메시지**:
- 우측 정렬 (`items-end`)
- 파란색 배경 (`bg-blue-600 text-white`)

**타인의 메시지**:
- 좌측 정렬 (`items-start`)
- 회색 배경 (`bg-gray-700 text-gray-100`)

---

## 알고리즘: 연속 메시지 그룹화

### 목적

같은 사용자가 짧은 시간 내에 보낸 여러 메시지를 시각적으로 그룹화하여 가독성 향상.

### 규칙

| 조건 | 결과 |
|------|------|
| 다른 사용자 | 비그룹 (헤더 표시) |
| 같은 사용자 + 1분 이내 | 그룹화 (헤더 생략) |
| 같은 사용자 + 1분 초과 | 비그룹 (헤더 표시) |

### 구현 상세

```typescript
const isContinuousMessage = (index: number): boolean => {
  // 첫 메시지는 항상 비그룹
  if (index === 0) return false;

  const currentMsg = messages[index];
  const prevMsg = messages[index - 1];

  // 같은 사용자가 아니면 비그룹
  if (currentMsg.userId !== prevMsg.userId) return false;

  // 시간 차이 계산 (1분 = 60000ms)
  try {
    const currentTime = new Date(currentMsg.createdAt).getTime();
    const prevTime = new Date(prevMsg.createdAt).getTime();
    return currentTime - prevTime < 60000;
  } catch {
    // ISO 8601 파싱 실패 시 비그룹
    return false;
  }
};
```

### UI 렌더링

```tsx
{messages.map((message, index) => {
  const isOwn = currentUserId === message.userId;
  const isContinuous = isContinuousMessage(index);

  return (
    <div className={`flex flex-col ${isOwn ? 'items-end' : 'items-start'}
                     ${isContinuous ? 'mt-0.5' : ''}`}>
      {/* 헤더: 비연속 메시지만 표시 */}
      {!isContinuous && (
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-gray-400">{message.userName}</span>
          <span className="text-xs text-gray-500">{formatTime(message.createdAt)}</span>
        </div>
      )}

      {/* 메시지 본문 */}
      <div className={/* ... */}>
        <MarkdownRenderer content={message.content} />
      </div>
    </div>
  );
})}
```

---

## Markdown 지원

### 지원 문법

| 문법 | 렌더링 |
|------|--------|
| `# 제목` | `<h1>제목</h1>` |
| `**굵게**` | `<strong>굵게</strong>` |
| `*기울임*` | `<em>기울임</em>` |
| `` `코드` `` | `<code>코드</code>` |
| `[링크](url)` | `<a href="url">링크</a>` |
| ` ```js ... ``` ` | `<pre><code class="language-js">...</code></pre>` |
| `- 리스트` | `<ul><li>리스트</li></ul>` |

### 렌더링 라이브러리

**컴포넌트**: `/frontend/src/components/ui/MarkdownRenderer.tsx`

```typescript
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function MarkdownRenderer({ content, className }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className={`prose prose-sm ${className}`}
      components={{
        // 커스텀 렌더러 (링크 새 창 열기 등)
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
```

**플러그인**:
- `remark-gfm`: GitHub Flavored Markdown (테이블, 체크리스트 등)

**스타일링**:
- Tailwind Typography (`prose` 클래스)
- 채팅 버블에 맞게 여백 조정: `prose-p:my-0 prose-headings:my-1`
- 다크 모드: `prose-invert`

---

## 성능 최적화

### 1. 페이지네이션

**기본 설정**:
- 기본 limit: 100개
- 최대 limit: 500개

**DB 쿼리**:
```python
query = (
    select(ChatMessage)
    .options(selectinload(ChatMessage.user))  # N+1 방지
    .where(ChatMessage.meeting_id == meeting_id)
    .order_by(ChatMessage.created_at.desc())
    .offset((page - 1) * limit)
    .limit(limit)
)
```

### 2. Eager Loading

User 정보를 eager loading하여 N+1 쿼리 방지:
```python
.options(selectinload(ChatMessage.user))
```

### 3. 인덱스

**테이블 인덱스**:
- `meeting_id`: 회의별 메시지 조회 최적화
- `created_at`: 시간순 정렬 최적화

### 4. 낙관적 업데이트

자신의 메시지는 전송 즉시 로컬 스토어에 추가하여 UI 반응 속도 향상:
```typescript
sendDataPacket({ /* ... */ });
addChatMessage({ /* ... */ });  // 즉시 로컬 추가
```

---

## 보안

### 1. 권한 검증

**API 엔드포인트**:
```python
@router.get("/{meeting_id}/chat")
async def get_chat_messages(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    # ...
):
```

**검증 내용**:
- JWT 토큰 유효성 (인증)
- 회의 참여자 여부 (인가)
- 회의 존재 여부

### 2. 입력 검증

**클라이언트**:
```typescript
const trimmedValue = inputValue.trim();
if (!trimmedValue) return;  // 빈 메시지 방지
```

**서버**:
```python
content = content.strip()
if not content:
    raise ValueError("Message content cannot be empty")
```

### 3. XSS 방지

Markdown 렌더링 시 `react-markdown`이 자동으로 HTML sanitization 수행:
- `<script>` 태그 제거
- `javascript:` 프로토콜 차단
- 위험한 HTML 속성 제거

---

## 에러 처리

### 클라이언트

**전송 실패**:
```typescript
const sendChatMessage = useCallback((content: string) => {
  const room = roomRef.current;
  if (!room || room.state !== LiveKitConnectionState.Connected) {
    logger.warn('[useLiveKit] Cannot send chat: not connected');
    return;  // 조용한 실패 (사용자에게 알림 없음)
  }
  // ...
});
```

**히스토리 로드 실패**:
```typescript
try {
  const response = await api.get(`/meetings/${meetingId}/chat`);
  setChatMessages(response.data.messages);
} catch (err) {
  logger.warn('[useLiveKit] Failed to fetch chat history:', err);
  // 빈 배열 유지 (기존 메시지 그대로)
}
```

### 서버

**빈 메시지**:
```python
if not content:
    raise ValueError("Message content cannot be empty")
```

**권한 없음**:
```python
# require_meeting_participant 의존성에서 처리
raise HTTPException(status_code=403, detail="Not a participant")
```

---

## 미래 확장

### 1. 메시지 편집/삭제

**현재**: 전송 후 수정 불가

**확장**:
- 메시지 편집 API 추가
- DataPacket으로 편집 이벤트 브로드캐스트
- UI에 편집됨 표시

### 2. 이미지/파일 첨부

**확장**:
- MinIO 업로드 API
- Markdown 이미지 문법: `![alt](url)`
- DataPacket에 파일 메타데이터 포함

### 3. 읽음 표시

**확장**:
- `read_receipts` 테이블 추가
- 읽음 시간 추적
- UI에 읽음/안 읽음 표시

### 4. 멘션 (@mention)

**확장**:
- `@userName` 구문 파싱
- 멘션된 사용자에게 알림
- Markdown 렌더러에서 하이라이트

### 5. 메시지 검색

**확장**:
- 전문 검색 (PostgreSQL FTS)
- 날짜 범위 필터
- 발신자 필터

### 6. Thread/Reply

**확장**:
- `parent_message_id` 컬럼 추가
- 스레드 UI (Slack 스타일)
- 답장 알림

---

## 참고 자료

### 관련 파일

**백엔드**:
- `/backend/app/models/chat.py` - 데이터 모델
- `/backend/app/services/chat_service.py` - 비즈니스 로직
- `/backend/app/api/v1/endpoints/chat.py` - REST API
- `/backend/app/api/v1/endpoints/livekit_webhooks.py` - LiveKit 이벤트 처리

**프론트엔드**:
- `/frontend/src/types/chat.ts` - 타입 정의
- `/frontend/src/components/meeting/ChatPanel.tsx` - UI 컴포넌트
- `/frontend/src/components/ui/MarkdownRenderer.tsx` - Markdown 렌더러
- `/frontend/src/hooks/useLiveKit.ts` - LiveKit 통합
- `/frontend/src/stores/meetingRoomStore.ts` - 상태 관리

### 외부 문서

- [LiveKit DataPacket API](https://docs.livekit.io/realtime/client/data-messages/)
- [react-markdown Documentation](https://github.com/remarkjs/react-markdown)
- [GitHub Flavored Markdown Spec](https://github.github.com/gfm/)

---

## 체크리스트

### 구현 완료

- [x] ChatMessage 모델 정의
- [x] ChatService CRUD 구현
- [x] GET /chat API 엔드포인트
- [x] LiveKit DataPacket 전송/수신
- [x] 채팅 히스토리 로드
- [x] ChatPanel 컴포넌트
- [x] Markdown 렌더링
- [x] 연속 메시지 그룹화
- [x] 자동 스크롤
- [x] 키보드 단축키

### 미구현

- [ ] 메시지 편집/삭제
- [ ] 이미지/파일 첨부
- [ ] 읽음 표시
- [ ] 멘션 (@mention)
- [ ] 메시지 검색
- [ ] Thread/Reply
- [ ] LiveKit Webhook에서 채팅 DB 저장 (현재는 클라이언트 전용)
