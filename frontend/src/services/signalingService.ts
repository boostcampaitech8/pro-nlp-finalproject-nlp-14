/**
 * WebSocket 시그널링 서비스
 * 서버와의 시그널링 메시지 송수신 담당
 */

import type { ClientMessage, ServerMessage } from '@/types/webrtc';
import logger from '@/utils/logger';

type MessageHandler = (message: ServerMessage) => void;

const RECONNECT_DELAY = 1000;
const MAX_RECONNECT_ATTEMPTS = 5;
const SEND_RETRY_DELAY = 50;
const SEND_MAX_RETRIES = 10;

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
        logger.log('[Signaling] Connected');
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onerror = (error) => {
        logger.error('[Signaling] Error:', error);
        reject(error);
      };

      this.ws.onclose = (event) => {
        logger.log('[Signaling] Closed:', event.code, event.reason);

        if (!this.isClosedIntentionally && this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          this.scheduleReconnect();
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as ServerMessage;
          logger.log('[Signaling] Received:', message.type);
          this.messageHandler?.(message);
        } catch (error) {
          logger.error('[Signaling] Failed to parse message:', error);
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

    logger.log(`[Signaling] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(async () => {
      try {
        await this.createConnection();
        // 재연결 후 join 메시지 전송
        this.send({ type: 'join' });
      } catch (error) {
        logger.error('[Signaling] Reconnection failed:', error);
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
   * 메시지 전송 (재시도 로직 포함)
   */
  send(message: ClientMessage): void {
    this.sendWithRetry(message, 0);
  }

  /**
   * 재시도 로직이 포함된 메시지 전송
   */
  private sendWithRetry(message: ClientMessage, retryCount: number): void {
    // WebSocket이 OPEN 상태면 즉시 전송
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      logger.log('[Signaling] Sending:', message.type);
      this.ws.send(JSON.stringify(message));
      return;
    }

    // 연결 중(CONNECTING)이고 재시도 횟수가 남았으면 재시도
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING && retryCount < SEND_MAX_RETRIES) {
      logger.log(`[Signaling] WebSocket connecting, retry ${retryCount + 1}/${SEND_MAX_RETRIES} for:`, message.type);
      setTimeout(() => {
        this.sendWithRetry(message, retryCount + 1);
      }, SEND_RETRY_DELAY);
      return;
    }

    // 전송 불가
    logger.warn('[Signaling] Cannot send - not connected, message:', message.type);
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
