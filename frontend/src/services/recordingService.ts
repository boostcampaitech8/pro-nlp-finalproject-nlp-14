import type { Recording, RecordingDownloadResponse, RecordingListResponse } from '@/types';
import api from './api';

export interface RecordingUploadParams {
  meetingId: string;
  file: Blob;
  startedAt: Date;
  endedAt: Date;
  durationMs: number;
}

export const recordingService = {
  /**
   * 회의 녹음 목록 조회
   */
  async listRecordings(meetingId: string): Promise<RecordingListResponse> {
    const response = await api.get<RecordingListResponse>(
      `/meetings/${meetingId}/recordings`
    );
    return response.data;
  },

  /**
   * 녹음 다운로드 URL 조회 (deprecated - presigned URL 문제로 사용하지 않음)
   */
  async getDownloadUrl(
    meetingId: string,
    recordingId: string
  ): Promise<RecordingDownloadResponse> {
    const response = await api.get<RecordingDownloadResponse>(
      `/meetings/${meetingId}/recordings/${recordingId}/download`
    );
    return response.data;
  },

  /**
   * 녹음 파일 직접 다운로드 (권장)
   */
  async downloadFile(meetingId: string, recordingId: string): Promise<Blob> {
    const response = await api.get<Blob>(
      `/meetings/${meetingId}/recordings/${recordingId}/file`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },

  /**
   * 녹음 파일 업로드
   */
  async uploadRecording(params: RecordingUploadParams): Promise<Recording> {
    const formData = new FormData();
    formData.append('file', params.file, 'recording.webm');
    formData.append('startedAt', params.startedAt.toISOString());
    formData.append('endedAt', params.endedAt.toISOString());
    formData.append('durationMs', params.durationMs.toString());

    const response = await api.post<Recording>(
      `/meetings/${params.meetingId}/recordings`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },
};
