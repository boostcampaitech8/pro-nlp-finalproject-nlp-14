import type {
  MeetingTranscript,
  TranscribeRequest,
  TranscribeResponse,
  TranscriptDownloadResponse,
  TranscriptStatusResponse,
} from '@/types';
import api from './api';

export const transcriptService = {
  /**
   * 회의 STT 변환 시작
   * 모든 완료된 녹음에 대해 비동기로 STT 작업을 시작합니다.
   */
  async startTranscription(
    meetingId: string,
    language: string = 'ko'
  ): Promise<TranscribeResponse> {
    const request: TranscribeRequest = { language };
    const response = await api.post<TranscribeResponse>(
      `/meetings/${meetingId}/transcribe`,
      request
    );
    return response.data;
  },

  /**
   * STT 변환 진행 상태 조회
   */
  async getTranscriptionStatus(
    meetingId: string
  ): Promise<TranscriptStatusResponse> {
    const response = await api.get<TranscriptStatusResponse>(
      `/meetings/${meetingId}/transcript/status`
    );
    return response.data;
  },

  /**
   * 회의 트랜스크립트 조회
   * 화자별 병합된 전체 트랜스크립트를 조회합니다.
   */
  async getTranscript(meetingId: string): Promise<MeetingTranscript> {
    const response = await api.get<MeetingTranscript>(
      `/meetings/${meetingId}/transcripts`
    );
    return response.data;
  },

  /**
   * STT 진행 상태를 폴링으로 확인
   * 완료될 때까지 주기적으로 상태를 확인합니다.
   */
  async waitForTranscription(
    meetingId: string,
    options: {
      intervalMs?: number;
      timeoutMs?: number;
      onProgress?: (status: TranscriptStatusResponse) => void;
    } = {}
  ): Promise<MeetingTranscript> {
    const { intervalMs = 3000, timeoutMs = 600000, onProgress } = options;
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const status = await this.getTranscriptionStatus(meetingId);

      if (onProgress) {
        onProgress(status);
      }

      if (status.status === 'completed') {
        return this.getTranscript(meetingId);
      }

      if (status.status === 'failed') {
        throw new Error(status.error || 'STT 변환에 실패했습니다.');
      }

      // 진행 중인 경우 대기 후 재확인
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }

    throw new Error('STT 변환 시간이 초과되었습니다.');
  },

  /**
   * 회의록 다운로드 URL 조회
   */
  async getDownloadUrl(meetingId: string): Promise<TranscriptDownloadResponse> {
    const response = await api.get<TranscriptDownloadResponse>(
      `/meetings/${meetingId}/transcript/download`
    );
    return response.data;
  },

  /**
   * 회의록 파일 다운로드
   */
  async downloadTranscript(meetingId: string): Promise<void> {
    const { downloadUrl } = await this.getDownloadUrl(meetingId);

    // 새 탭에서 다운로드
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `transcript_${meetingId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },
};
