import type { Recording, RecordingDownloadResponse, RecordingListResponse } from '@/types';
import type { VADMetadata } from '@/hooks/useVAD';
import api from './api';

export interface RecordingUploadParams {
  meetingId: string;
  file: Blob;
  startedAt: Date;
  endedAt: Date;
  durationMs: number;
  vadMetadata?: VADMetadata;  // 클라이언트 VAD 메타데이터 (선택)
}

// Presigned URL 업로드 응답 타입
export interface RecordingUploadUrlResponse {
  recordingId: string;
  uploadUrl: string;
  filePath: string;
  expiresInSeconds: number;
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
   * 녹음 파일 업로드 (기존 방식 - deprecated)
   * nginx 파일 크기 제한으로 대용량 파일 업로드 실패 가능
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

  /**
   * Presigned URL로 녹음 파일 업로드 (권장)
   * 대용량 파일을 MinIO에 직접 업로드하여 nginx 제한 우회
   *
   * 흐름:
   * 1. Backend에서 presigned URL 발급
   * 2. MinIO에 직접 업로드
   * 3. Backend에 업로드 완료 확인
   */
  async uploadRecordingPresigned(
    params: RecordingUploadParams,
    onProgress?: (progress: number) => void
  ): Promise<Recording> {
    const fileSize = params.file.size;

    // 1. Presigned URL 요청 (VAD 메타데이터 포함)
    const urlResponse = await api.post<RecordingUploadUrlResponse>(
      `/meetings/${params.meetingId}/recordings/upload-url`,
      {
        startedAt: params.startedAt.toISOString(),
        endedAt: params.endedAt.toISOString(),
        durationMs: params.durationMs,
        fileSizeBytes: fileSize,
        vadMetadata: params.vadMetadata || null,
      }
    );

    const { recordingId, uploadUrl } = urlResponse.data;

    // 2. MinIO에 직접 업로드 (fetch 사용 - axios는 presigned URL과 호환성 문제)
    try {
      const uploadResponse = await new Promise<Response>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', uploadUrl, true);
        xhr.setRequestHeader('Content-Type', 'audio/webm');

        // 업로드 진행률
        if (onProgress) {
          xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
              const progress = Math.round((event.loaded / event.total) * 100);
              onProgress(progress);
            }
          };
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(new Response(null, { status: xhr.status }));
          } else {
            reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
          }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.ontimeout = () => reject(new Error('Upload timeout'));

        xhr.send(params.file);
      });

      if (!uploadResponse.ok) {
        throw new Error(`Upload failed: ${uploadResponse.status}`);
      }
    } catch (error) {
      console.error('Failed to upload to MinIO:', error);
      throw new Error('Failed to upload recording file');
    }

    // 3. 업로드 완료 확인
    const confirmResponse = await api.post<Recording>(
      `/meetings/${params.meetingId}/recordings/${recordingId}/confirm`
    );

    return confirmResponse.data;
  },
};
