/**
 * Spotlight API Client
 * Handles session CRUD operations and SSE chat streaming
 */

import api from '@/services/api';

export interface SpotlightSession {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface SpotlightMessage {
  role: 'user' | 'assistant';
  content: string;
  type?: 'text' | 'hitl';
  hitl_status?: 'pending' | 'confirmed' | 'cancelled';
  hitl_data?: {
    tool_name: string;
    params: Record<string, unknown>;
    params_display?: Record<string, string>;
    message: string;
    required_fields?: Array<{
      name: string;
      description: string;
      type: string;
      required: boolean;
    }>;
    display_template?: string;
  };
}

export interface HITLRequiredField {
  name: string;
  description: string;
  type: string;
  required: boolean;
}

export interface SSEEvent {
  type: 'message' | 'status' | 'done' | 'error' | 'hitl_request';
  data?: string;
  error?: string;
  // HITL 전용 필드 (hitl_request 이벤트에서 사용)
  tool_name?: string;
  params?: Record<string, unknown>;
  params_display?: Record<string, string>; // UUID → 이름 변환된 표시용 값
  message?: string;
  required_fields?: HITLRequiredField[];
  display_template?: string; // 자연어 템플릿 ({{param}}이 input으로 대체됨)
}

const API_BASE = '/spotlight';

// SSE reconnection configuration
const SSE_RECONNECT_CONFIG = {
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  maxRetries: 5,
  backoffMultiplier: 2,
};

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function getAuthToken(): string {
  return localStorage.getItem('accessToken') || '';
}

class SSEParser {
  private buffer = '';

  parse(chunk: string): SSEEvent[] {
    this.buffer += chunk;
    const events: SSEEvent[] = [];

    // 완전한 이벤트들만 처리 (\n\n으로 끝나는 것)
    const parts = this.buffer.split('\n\n');

    // 마지막 부분은 불완전할 수 있으므로 버퍼에 유지
    this.buffer = parts.pop() || '';

    for (const part of parts) {
      if (!part.trim()) continue;

      const event: Partial<SSEEvent> = {};
      const lines = part.split('\n');

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          event.type = line.slice(7).trim() as SSEEvent['type'];
        } else if (line.startsWith('data: ')) {
          // SSE spec: 여러 data: 필드는 줄바꿈으로 연결
          if (event.data !== undefined) {
            event.data += '\n' + line.slice(6);
          } else {
            event.data = line.slice(6);
          }
        }
      }

      if (event.type) {
        // hitl_request 이벤트는 JSON 파싱
        if (event.type === 'hitl_request' && event.data) {
          try {
            const hitlData = JSON.parse(event.data);
            event.tool_name = hitlData.tool_name;
            event.params = hitlData.params;
            event.params_display = hitlData.params_display; // UUID → 이름 변환된 표시용 값
            event.message = hitlData.message;
            event.required_fields = hitlData.required_fields;
            event.display_template = hitlData.display_template; // 자연어 템플릿
          } catch {
            console.error('Failed to parse HITL data:', event.data);
          }
        }
        events.push(event as SSEEvent);
      }
    }

    return events;
  }

  reset() {
    this.buffer = '';
  }
}

export const spotlightApi = {
  // Session CRUD operations
  async createSession(): Promise<SpotlightSession> {
    const response = await api.post<SpotlightSession>(`${API_BASE}/sessions`);
    return response.data;
  },

  async listSessions(): Promise<SpotlightSession[]> {
    const response = await api.get<SpotlightSession[]>(`${API_BASE}/sessions`);
    return response.data;
  },

  async getSession(id: string): Promise<SpotlightSession> {
    const response = await api.get<SpotlightSession>(`${API_BASE}/sessions/${id}`);
    return response.data;
  },

  async deleteSession(id: string): Promise<void> {
    await api.delete(`${API_BASE}/sessions/${id}`);
  },

  async updateSessionTitle(id: string, title: string): Promise<SpotlightSession> {
    const response = await api.patch<SpotlightSession>(`${API_BASE}/sessions/${id}`, { title });
    return response.data;
  },

  async getSessionMessages(id: string): Promise<SpotlightMessage[]> {
    const response = await api.get<SpotlightMessage[]>(`${API_BASE}/sessions/${id}/messages`);
    return response.data;
  },

  // SSE chat streaming (POST + fetch API)
  async chatStream(
    sessionId: string,
    message: string,
    onEvent: (event: SSEEvent) => void,
    hitlAction?: 'confirm' | 'cancel',
    hitlParams?: Record<string, unknown>,
  ): Promise<AbortController> {
    const controller = new AbortController();
    const token = getAuthToken();

    // HITL 응답 시 hitl_action 및 hitl_params 포함
    const body: { message: string; hitl_action?: string; hitl_params?: Record<string, unknown> } = { message };
    if (hitlAction) {
      body.hitl_action = hitlAction;
    }
    if (hitlParams) {
      body.hitl_params = hitlParams;
    }

    const response = await fetch(
      `/api/v1${API_BASE}/sessions/${sessionId}/chat?token=${encodeURIComponent(token)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      if (response.status === 404) {
        onEvent({ type: 'error', error: '세션이 만료되었습니다.' });
        throw new Error('SESSION_NOT_FOUND');
      }
      if (response.status === 401) {
        onEvent({ type: 'error', error: '인증이 만료되었습니다. 다시 로그인해주세요.' });
        throw new Error('UNAUTHORIZED');
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    const parser = new SSEParser();

    // SSE parsing loop (async)
    (async () => {
      try {
        while (reader) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          parser.parse(chunk).forEach(onEvent);
        }
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          onEvent({ type: 'error', error: String(error) });
        }
      } finally {
        parser.reset();
      }
    })();

    return controller;
  },

  // Chat stream with automatic retry
  async chatStreamWithRetry(
    sessionId: string,
    message: string,
    onEvent: (event: SSEEvent) => void,
    hitlAction?: 'confirm' | 'cancel',
    hitlParams?: Record<string, unknown>,
    retryCount = 0,
  ): Promise<void> {
    try {
      await this.chatStream(sessionId, message, onEvent, hitlAction, hitlParams);
    } catch (error) {
      const errorMessage = (error as Error).message;
      // Don't retry on auth errors
      if (errorMessage === 'SESSION_NOT_FOUND' || errorMessage === 'UNAUTHORIZED') {
        return;
      }

      if (retryCount >= SSE_RECONNECT_CONFIG.maxRetries) {
        onEvent({ type: 'error', error: '연결 재시도 횟수 초과' });
        return;
      }

      const delay = Math.min(
        SSE_RECONNECT_CONFIG.initialDelayMs * Math.pow(SSE_RECONNECT_CONFIG.backoffMultiplier, retryCount),
        SSE_RECONNECT_CONFIG.maxDelayMs
      );

      onEvent({ type: 'status', data: `재연결 중... (${retryCount + 1}/${SSE_RECONNECT_CONFIG.maxRetries})` });
      await sleep(delay);
      return this.chatStreamWithRetry(sessionId, message, onEvent, hitlAction, hitlParams, retryCount + 1);
    }
  },
};
