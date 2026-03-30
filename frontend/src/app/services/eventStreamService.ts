// Event Stream Service - SSE 연결 및 이벤트 파싱
// 표준 SSE 포맷 지원: event: status|message|done|error

export enum EventType {
  STATUS = 'status',
  MESSAGE = 'message',
  DONE = 'done',
  ERROR = 'error',
}

export interface StreamEvent {
  type: EventType;
  content?: string;
  error?: string;
  timestamp?: string;
}

/**
 * Agent 스트리밍 이벤트를 SSE로 수신
 * @param meetingId 회의 ID
 * @param transcriptId 발화 ID
 */
export async function* streamAgentEvents(
  meetingId: string,
  transcriptId: string
): AsyncGenerator<StreamEvent, void, unknown> {
  // 인증 토큰 가져오기
  const token = localStorage.getItem('access_token');
  if (!token) {
    throw new Error('인증 토큰이 없습니다');
  }

  const response = await fetch('/api/v1/agent/meeting', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      meetingId,
      transcriptId,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  if (!response.body) {
    throw new Error('Response body is null');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentEventType: EventType | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');

      // 마지막 불완전한 부분은 버퍼에 유지
      buffer = parts.pop() || '';

      for (const part of parts) {
        const lines = part.split('\n').filter((l) => l.trim());

        for (const line of lines) {
          // SSE 이벤트 타입 파싱
          if (line.startsWith('event: ')) {
            const eventTypeStr = line.slice(7).trim();
            // 이벤트 타입을 enum 값으로 변환
            if (eventTypeStr === 'status') {
              currentEventType = EventType.STATUS;
            } else if (eventTypeStr === 'message') {
              currentEventType = EventType.MESSAGE;
            } else if (eventTypeStr === 'done') {
              currentEventType = EventType.DONE;
            } else if (eventTypeStr === 'error') {
              currentEventType = EventType.ERROR;
            }
          }
          // SSE 데이터 파싱
          else if (line.startsWith('data: ')) {
            const data = line.slice(6); // trim() 제거하여 띄어쓰기 토큰 보존

            // 완료 신호
            if (data === '[DONE]') {
              return;
            }

            // 에러 신호
            if (data.startsWith('[ERROR]')) {
              const error = data.slice(8);
              yield {
                type: EventType.ERROR,
                error,
              };
              throw new Error(error);
            }

            // 현재 이벤트 타입으로 데이터 전송
            const eventType = currentEventType || EventType.MESSAGE;
            yield {
              type: eventType,
              content: data,
            };

            // 이벤트 전송 후 타입 초기화 (다음 이벤트와 혼동 방지)
            currentEventType = null;

            // 완료/에러 이벤트면 종료
            if (eventType === EventType.DONE) {
              return;
            }
            if (eventType === EventType.ERROR) {
              throw new Error(data);
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
