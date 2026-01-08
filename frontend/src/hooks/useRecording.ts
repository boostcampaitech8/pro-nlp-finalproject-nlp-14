/**
 * 녹음 훅
 * MediaRecorder 기반 녹음 및 IndexedDB 저장, 서버 업로드 담당
 */

import { useCallback, useRef, useState, useEffect } from 'react';
import { recordingService } from '@/services/recordingService';
import { recordingStorageService } from '@/services/recordingStorageService';
import { ensureValidToken } from '@/services/api';
import logger from '@/utils/logger';

// 녹음 임시 저장 주기 (10초)
const RECORDING_SAVE_INTERVAL = 10 * 1000;

interface UseRecordingOptions {
  meetingId: string;
  getLocalStream: () => MediaStream | null;
}

interface UseRecordingReturn {
  // 상태
  isRecording: boolean;
  recordingError: string | null;
  isUploading: boolean;
  uploadProgress: number;

  // 액션
  startRecording: () => void;
  stopRecording: () => Promise<void>;
  uploadPendingRecordings: () => Promise<void>;
}

export function useRecording({
  meetingId,
  getLocalStream,
}: UseRecordingOptions): UseRecordingReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingStartTimeRef = useRef<Date | null>(null);
  const recordingIdRef = useRef<string | null>(null);
  const saveIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastSavedChunkIndexRef = useRef<number>(-1);

  /**
   * 녹음 청크를 IndexedDB에 증분 저장
   */
  const saveChunksToStorage = useCallback(async () => {
    if (!recordingIdRef.current || !recordingStartTimeRef.current) return;
    if (recordedChunksRef.current.length === 0) return;

    try {
      const newLastIndex = await recordingStorageService.saveNewChunks(
        recordingIdRef.current,
        meetingId,
        recordedChunksRef.current,
        recordingStartTimeRef.current,
        lastSavedChunkIndexRef.current
      );
      lastSavedChunkIndexRef.current = newLastIndex;
    } catch (err) {
      logger.error('[useRecording] Failed to save chunks to storage:', err);
    }
  }, [meetingId]);

  /**
   * IndexedDB에 저장된 이전 녹음 데이터 업로드
   */
  const uploadPendingRecordings = useCallback(async () => {
    try {
      // 24시간 이상 된 오래된 녹음 정리
      await recordingStorageService.cleanupOldRecordings();

      // 현재 회의에 대한 대기 중인 녹음 조회
      const pendingRecordings = await recordingStorageService.getRecordingsByMeeting(meetingId);

      if (pendingRecordings.length === 0) {
        logger.log('[useRecording] No pending recordings to upload');
        // localStorage 백업도 확인
        const backupStr = localStorage.getItem('mit-recording-backup');
        if (backupStr) {
          try {
            const backup = JSON.parse(backupStr);
            if (backup.meetingId === meetingId) {
              logger.log('[useRecording] Found localStorage backup, but no chunks in IndexedDB');
              localStorage.removeItem('mit-recording-backup');
            }
          } catch {
            localStorage.removeItem('mit-recording-backup');
          }
        }
        return;
      }

      logger.log(`[useRecording] Found ${pendingRecordings.length} pending recordings to upload`);

      for (const recording of pendingRecordings) {
        if (recording.chunks.length === 0) {
          await recordingStorageService.deleteRecording(recording.id);
          continue;
        }

        try {
          await ensureValidToken();

          const blob = recordingStorageService.mergeChunks(recording.chunks);
          const endTime = new Date(recording.lastUpdatedAt);
          const durationMs = endTime.getTime() - new Date(recording.startedAt).getTime();

          logger.log(`[useRecording] Uploading pending recording ${recording.id}: ${blob.size} bytes`);

          await recordingService.uploadRecordingPresigned(
            {
              meetingId: recording.meetingId,
              file: blob,
              startedAt: new Date(recording.startedAt),
              endedAt: endTime,
              durationMs,
            },
            (progress) => {
              logger.log(`[useRecording] Pending upload progress: ${progress}%`);
            }
          );

          await recordingStorageService.deleteRecording(recording.id);
          logger.log(`[useRecording] Pending recording ${recording.id} uploaded and deleted`);
        } catch (err) {
          logger.error(`[useRecording] Failed to upload pending recording ${recording.id}:`, err);
        }
      }

      localStorage.removeItem('mit-recording-backup');
    } catch (err) {
      logger.error('[useRecording] Failed to process pending recordings:', err);
    }
  }, [meetingId]);

  /**
   * 녹음 시작
   */
  const startRecording = useCallback(() => {
    if (isRecording || mediaRecorderRef.current) {
      logger.log('[useRecording] Already recording');
      return;
    }

    const localStream = getLocalStream();
    if (!localStream) {
      logger.error('[useRecording] No local stream for recording');
      setRecordingError('로컬 오디오 스트림이 없습니다.');
      return;
    }

    // 초기화
    setRecordingError(null);
    recordedChunksRef.current = [];
    lastSavedChunkIndexRef.current = -1;

    // 녹음 ID 생성
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    recordingIdRef.current = `${meetingId}_${timestamp}`;

    try {
      logger.log('[useRecording] Starting recording with MediaRecorder...');

      // MediaRecorder 생성
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';

      const mediaRecorder = new MediaRecorder(localStream, {
        mimeType,
        audioBitsPerSecond: 128000,
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onerror = (event) => {
        logger.error('[useRecording] MediaRecorder error:', event);
        setRecordingError('녹음 중 오류가 발생했습니다.');
        setIsRecording(false);
        if (saveIntervalRef.current) {
          clearInterval(saveIntervalRef.current);
          saveIntervalRef.current = null;
        }
      };

      mediaRecorder.onstop = () => {
        logger.log('[useRecording] MediaRecorder stopped');
        if (saveIntervalRef.current) {
          clearInterval(saveIntervalRef.current);
          saveIntervalRef.current = null;
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      recordingStartTimeRef.current = new Date();

      // 녹음 시작 (1초마다 데이터 수집)
      mediaRecorder.start(1000);
      setIsRecording(true);

      // 주기적으로 IndexedDB에 저장
      saveIntervalRef.current = setInterval(() => {
        saveChunksToStorage();
      }, RECORDING_SAVE_INTERVAL);

      logger.log('[useRecording] Recording started with periodic save');
    } catch (err) {
      logger.error('[useRecording] Failed to start recording:', err);
      setRecordingError('녹음을 시작할 수 없습니다.');
      mediaRecorderRef.current = null;
      recordingIdRef.current = null;
    }
  }, [isRecording, meetingId, getLocalStream, saveChunksToStorage]);

  /**
   * 녹음 중지 및 서버 업로드
   */
  const stopRecording = useCallback(async (): Promise<void> => {
    // 주기적 저장 중지
    if (saveIntervalRef.current) {
      clearInterval(saveIntervalRef.current);
      saveIntervalRef.current = null;
    }

    if (!mediaRecorderRef.current || !recordingStartTimeRef.current) {
      logger.log('[useRecording] No active recording');
      return;
    }

    logger.log('[useRecording] Stopping recording and uploading...');
    const currentRecordingId = recordingIdRef.current;
    const startTime = recordingStartTimeRef.current;

    return new Promise<void>((resolve) => {
      const mediaRecorder = mediaRecorderRef.current!;

      mediaRecorder.onstop = async () => {
        const endTime = new Date();
        const durationMs = endTime.getTime() - startTime.getTime();

        // 1. 메모리의 남은 청크를 IndexedDB에 증분 저장
        if (currentRecordingId && recordedChunksRef.current.length > lastSavedChunkIndexRef.current + 1) {
          try {
            await recordingStorageService.saveNewChunks(
              currentRecordingId,
              meetingId,
              recordedChunksRef.current,
              startTime,
              lastSavedChunkIndexRef.current
            );
            logger.log('[useRecording] Saved remaining chunks to IndexedDB before upload');
          } catch (err) {
            logger.error('[useRecording] Failed to save remaining chunks:', err);
          }
        }

        // 2. IndexedDB에서 모든 청크 조회하여 병합
        let allChunks: Blob[] = recordedChunksRef.current;
        if (currentRecordingId) {
          try {
            const storedChunks = await recordingStorageService.getChunks(currentRecordingId);
            if (storedChunks.length > 0) {
              allChunks = storedChunks;
              logger.log(`[useRecording] Retrieved ${storedChunks.length} chunks from IndexedDB`);
            }
          } catch (err) {
            logger.error('[useRecording] Failed to get chunks from IndexedDB, using memory chunks:', err);
          }
        }

        // 3. 청크 병합하여 Blob 생성
        const blob = recordingStorageService.mergeChunks(allChunks);
        logger.log(`[useRecording] Recording blob created: ${blob.size} bytes, ${durationMs}ms, ${allChunks.length} chunks`);

        // 4. 업로드
        if (blob.size > 0) {
          setIsUploading(true);
          setUploadProgress(0);
          try {
            await ensureValidToken();

            await recordingService.uploadRecordingPresigned(
              {
                meetingId,
                file: blob,
                startedAt: startTime,
                endedAt: endTime,
                durationMs,
              },
              (progress) => {
                setUploadProgress(progress);
                logger.log(`[useRecording] Upload progress: ${progress}%`);
              }
            );
            logger.log('[useRecording] Recording uploaded successfully');

            if (currentRecordingId) {
              await recordingStorageService.deleteRecording(currentRecordingId);
              logger.log('[useRecording] Deleted recording from IndexedDB:', currentRecordingId);
            }
          } catch (err) {
            logger.error('[useRecording] Failed to upload recording:', err);
            setRecordingError('녹음 업로드에 실패했습니다.');
            logger.log('[useRecording] Recording saved in IndexedDB for retry');
          } finally {
            setIsUploading(false);
            setUploadProgress(0);
          }
        }

        // 5. 상태 초기화
        mediaRecorderRef.current = null;
        recordingStartTimeRef.current = null;
        recordedChunksRef.current = [];
        recordingIdRef.current = null;
        lastSavedChunkIndexRef.current = -1;
        setIsRecording(false);

        resolve();
      };

      // 녹음 중지
      if (mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
      } else {
        mediaRecorderRef.current = null;
        recordingStartTimeRef.current = null;
        recordedChunksRef.current = [];
        recordingIdRef.current = null;
        lastSavedChunkIndexRef.current = -1;
        setIsRecording(false);
        resolve();
      }
    });
  }, [meetingId]);

  /**
   * beforeunload 이벤트 - 새로고침/탭 닫기 시 녹음 데이터 임시저장
   */
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (recordingIdRef.current && recordingStartTimeRef.current && recordedChunksRef.current.length > 0) {
        try {
          const backupData = {
            id: recordingIdRef.current,
            meetingId,
            startedAt: recordingStartTimeRef.current.toISOString(),
            chunkCount: recordedChunksRef.current.length,
            timestamp: Date.now(),
          };
          localStorage.setItem('mit-recording-backup', JSON.stringify(backupData));
          logger.log('[useRecording] Saved recording backup to localStorage');
        } catch (err) {
          logger.error('[useRecording] Failed to save recording backup:', err);
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [meetingId]);

  /**
   * cleanup
   */
  useEffect(() => {
    return () => {
      if (saveIntervalRef.current) {
        clearInterval(saveIntervalRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  return {
    isRecording,
    recordingError,
    isUploading,
    uploadProgress,
    startRecording,
    stopRecording,
    uploadPendingRecordings,
  };
}
