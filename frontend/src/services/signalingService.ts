/**
 * WebSocket 시그널링 서비스
 * 서버와의 시그널링 메시지 송수신 담당
 */

import type { ClientMessage, ServerMessage } from '@/types/webrtc';

type MessageHandler = (message: ServerMessage) => void;

const RECONNECT_DELAY = 1000;
const MAX_RECONNECT_ATTEMPTS = 5;

export class SignalingClient {
  private ws: WebSocket | null = null;
  private meetingId: string = '';
  private token: string = '';
  private messageHandler: MessageHandler | null = null;
  private reconnectAttempts = 0;
  private isClosedIntentionally = false;

  /**
   * WebSocket 연결
   */
  async connect(meetingId: string, token: string): Promise<void> {
    this.meetingId = meetingId;
    this.token = token;
    this.isClosedIntentionally = false;
    this.reconnectAttempts = 0;

    return this.createConnection();
  }

  /**
   * WebSocket 연결 생성
   */
  private createConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const url = `${protocol}//${host}/api/v1/meetings/${this.meetingId}/ws?token=${this.token}`;

      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('[Signaling] Connected');
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('[Signaling] Error:', error);
        reject(error);
      };

      this.ws.onclose = (event) => {
        console.log('[Signaling] Closed:', event.code, event.reason);

        if (!this.isClosedIntentionally && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          this.scheduleReconnect();
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as ServerMessage;
          console.log('[Signaling] Received:', message.type);
          this.messageHandler?.(message);
        } catch (error) {
          console.error('[Signaling] Failed to parse message:', error);
        }
      };
    });
  }

  /**
   * 재연결 스케줄링
   */
  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    const delay = RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`[Signaling] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(async () => {
      try {
        await this.createConnection();
        // 재연결 후 join 메시지 전송
        this.send({ type: 'join' });
      } catch (error) {
        console.error('[Signaling] Reconnection failed:', error);
      }
    }, delay);
  }

  /**
   * WebSocket 연결 해제
   */
  disconnect(): void {
    this.isClosedIntentionally = true;
    if (this.ws) {
      this.ws.close(1000, 'User disconnected');
      this.ws = null;
    }
  }

  /**
   * 메시지 전송
   */
  send(message: ClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[Signaling] Cannot send - not connected');
      return;
    }

    console.log('[Signaling] Sending:', message.type);
    this.ws.send(JSON.stringify(message));
  }

  /**
   * 메시지 핸들러 등록
   */
  onMessage(handler: MessageHandler): void {
    this.messageHandler = handler;
  }

  /**
   * 연결 상태 확인
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// 싱글톤 인스턴스
export const signalingClient = new SignalingClient();
