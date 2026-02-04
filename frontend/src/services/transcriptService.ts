import type { MeetingTranscript } from '@/types';
import api from './api';

export const transcriptService = {
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
};
