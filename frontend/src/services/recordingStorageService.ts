/**
 * IndexedDB 기반 녹음 임시 저장 서비스 (증분 저장 방식)
 * 새로고침/회의 종료 시에도 녹음 데이터를 보존
 */

import logger from '@/utils/logger';

const DB_NAME = 'mit-recordings';
const DB_VERSION = 2; // 버전 업그레이드 (스키마 변경)
const METADATA_STORE = 'recording-metadata';
const CHUNKS_STORE = 'recording-chunks';

// 녹음 메타데이터
export interface RecordingMetadata {
  id: string; // recordingId (meetingId_timestamp)
  meetingId: string;
  startedAt: Date;
  lastUpdatedAt: Date;
  chunkCount: number;
  totalSize: number;
}

// 개별 청크
export interface RecordingChunk {
  id: string; // recordingId_chunkIndex
  recordingId: string;
  chunkIndex: number;
  data: Blob;
  size: number;
  createdAt: Date;
}

// 조회용 통합 인터페이스 (기존 호환)
export interface PendingRecording {
  id: string;
  meetingId: string;
  chunks: Blob[];
  startedAt: Date;
  lastUpdatedAt: Date;
  totalSize: number;
}

class RecordingStorageService {
  private db: IDBDatabase | null = null;
  private dbReady: Promise<IDBDatabase>;

  constructor() {
    this.dbReady = this.initDB();
  }

  /**
   * IndexedDB 초기화
   */
  private initDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => {
        logger.error('[RecordingStorage] Failed to open IndexedDB:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        logger.log('[RecordingStorage] IndexedDB opened successfully');
        resolve(request.result);
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;

        // 기존 스토어 삭제 (스키마 변경)
        if (db.objectStoreNames.contains('pending-recordings')) {
          db.deleteObjectStore('pending-recordings');
        }
        if (db.objectStoreNames.contains(METADATA_STORE)) {
          db.deleteObjectStore(METADATA_STORE);
        }
        if (db.objectStoreNames.contains(CHUNKS_STORE)) {
          db.deleteObjectStore(CHUNKS_STORE);
        }

        // 메타데이터 스토어 생성
        const metadataStore = db.createObjectStore(METADATA_STORE, { keyPath: 'id' });
        metadataStore.createIndex('meetingId', 'meetingId', { unique: false });
        metadataStore.createIndex('startedAt', 'startedAt', { unique: false });

        // 청크 스토어 생성
        const chunksStore = db.createObjectStore(CHUNKS_STORE, { keyPath: 'id' });
        chunksStore.createIndex('recordingId', 'recordingId', { unique: false });
        chunksStore.createIndex('chunkIndex', 'chunkIndex', { unique: false });

        logger.log('[RecordingStorage] IndexedDB stores created (v2 - incremental)');
      };
    });
  }

  /**
   * DB 준비 대기
   */
  private async getDB(): Promise<IDBDatabase> {
    if (this.db) return this.db;
    return this.dbReady;
  }

  /**
   * 녹음 메타데이터 생성/업데이트
   */
  async saveMetadata(
    recordingId: string,
    meetingId: string,
    startedAt: Date,
    chunkCount: number,
    totalSize: number
  ): Promise<void> {
    const db = await this.getDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction([METADATA_STORE], 'readwrite');
      const store = transaction.objectStore(METADATA_STORE);

      const metadata: RecordingMetadata = {
        id: recordingId,
        meetingId,
        startedAt,
        lastUpdatedAt: new Date(),
        chunkCount,
        totalSize,
      };

      const request = store.put(metadata);

      request.onerror = () => {
        logger.error('[RecordingStorage] Failed to save metadata:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        resolve();
      };
    });
  }

  /**
   * 새로운 청크들만 증분 저장
   * @param recordingId 녹음 ID
   * @param meetingId 회의 ID
   * @param chunks 전체 청크 배열
   * @param startedAt 녹음 시작 시간
   * @param lastSavedIndex 마지막으로 저장된 청크 인덱스 (-1이면 처음)
   * @returns 새로 저장된 마지막 청크 인덱스
   */
  async saveNewChunks(
    recordingId: string,
    meetingId: string,
    chunks: Blob[],
    startedAt: Date,
    lastSavedIndex: number
  ): Promise<number> {
    if (chunks.length === 0 || lastSavedIndex >= chunks.length - 1) {
      return lastSavedIndex;
    }

    const db = await this.getDB();
    const newChunks = chunks.slice(lastSavedIndex + 1);
    let newTotalSize = 0;

    return new Promise((resolve, reject) => {
      const transaction = db.transaction([CHUNKS_STORE, METADATA_STORE], 'readwrite');
      const chunksStore = transaction.objectStore(CHUNKS_STORE);
      const metadataStore = transaction.objectStore(METADATA_STORE);

      // 새 청크들 저장
      newChunks.forEach((chunk, i) => {
        const chunkIndex = lastSavedIndex + 1 + i;
        const chunkData: RecordingChunk = {
          id: `${recordingId}_${chunkIndex}`,
          recordingId,
          chunkIndex,
          data: chunk,
          size: chunk.size,
          createdAt: new Date(),
        };
        chunksStore.put(chunkData);
        newTotalSize += chunk.size;
      });

      // 메타데이터 업데이트
      const metadataRequest = metadataStore.get(recordingId);
      metadataRequest.onsuccess = () => {
        const existing = metadataRequest.result as RecordingMetadata | undefined;
        const currentTotalSize = existing?.totalSize || 0;

        const metadata: RecordingMetadata = {
          id: recordingId,
          meetingId,
          startedAt,
          lastUpdatedAt: new Date(),
          chunkCount: chunks.length,
          totalSize: currentTotalSize + newTotalSize,
        };
        metadataStore.put(metadata);
      };

      transaction.oncomplete = () => {
        const newLastIndex = chunks.length - 1;
        logger.log(
          `[RecordingStorage] Saved ${newChunks.length} new chunks (index ${lastSavedIndex + 1}-${newLastIndex}, ${Math.round(newTotalSize / 1024)}KB)`
        );
        resolve(newLastIndex);
      };

      transaction.onerror = () => {
        logger.error('[RecordingStorage] Failed to save new chunks:', transaction.error);
        reject(transaction.error);
      };
    });
  }

  /**
   * 특정 녹음의 모든 청크 조회 (인덱스 순으로 정렬)
   */
  async getChunks(recordingId: string): Promise<Blob[]> {
    const db = await this.getDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction([CHUNKS_STORE], 'readonly');
      const store = transaction.objectStore(CHUNKS_STORE);
      const index = store.index('recordingId');
      const request = index.getAll(recordingId);

      request.onerror = () => {
        logger.error('[RecordingStorage] Failed to get chunks:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        const chunks = (request.result as RecordingChunk[]) || [];
        // 인덱스 순으로 정렬
        chunks.sort((a, b) => a.chunkIndex - b.chunkIndex);
        resolve(chunks.map((c) => c.data));
      };
    });
  }

  /**
   * 특정 녹음 메타데이터 조회
   */
  async getMetadata(recordingId: string): Promise<RecordingMetadata | null> {
    const db = await this.getDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction([METADATA_STORE], 'readonly');
      const store = transaction.objectStore(METADATA_STORE);
      const request = store.get(recordingId);

      request.onerror = () => {
        logger.error('[RecordingStorage] Failed to get metadata:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        resolve(request.result || null);
      };
    });
  }

  /**
   * 특정 녹음 데이터 조회 (메타데이터 + 청크)
   */
  async getRecording(recordingId: string): Promise<PendingRecording | null> {
    const metadata = await this.getMetadata(recordingId);
    if (!metadata) return null;

    const chunks = await this.getChunks(recordingId);

    return {
      id: metadata.id,
      meetingId: metadata.meetingId,
      chunks,
      startedAt: metadata.startedAt,
      lastUpdatedAt: metadata.lastUpdatedAt,
      totalSize: metadata.totalSize,
    };
  }

  /**
   * 특정 회의의 모든 녹음 데이터 조회
   */
  async getRecordingsByMeeting(meetingId: string): Promise<PendingRecording[]> {
    const db = await this.getDB();

    // 먼저 메타데이터 조회
    const metadataList = await new Promise<RecordingMetadata[]>((resolve, reject) => {
      const transaction = db.transaction([METADATA_STORE], 'readonly');
      const store = transaction.objectStore(METADATA_STORE);
      const index = store.index('meetingId');
      const request = index.getAll(meetingId);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result || []);
    });

    // 각 녹음의 청크 조회
    const recordings: PendingRecording[] = [];
    for (const metadata of metadataList) {
      const chunks = await this.getChunks(metadata.id);
      recordings.push({
        id: metadata.id,
        meetingId: metadata.meetingId,
        chunks,
        startedAt: metadata.startedAt,
        lastUpdatedAt: metadata.lastUpdatedAt,
        totalSize: metadata.totalSize,
      });
    }

    return recordings;
  }

  /**
   * 모든 대기 중인 녹음 메타데이터 조회
   */
  async getAllPendingMetadata(): Promise<RecordingMetadata[]> {
    const db = await this.getDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction([METADATA_STORE], 'readonly');
      const store = transaction.objectStore(METADATA_STORE);
      const request = store.getAll();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result || []);
    });
  }

  /**
   * 특정 녹음 데이터 삭제 (메타데이터 + 모든 청크)
   */
  async deleteRecording(recordingId: string): Promise<void> {
    const db = await this.getDB();

    // 먼저 청크 ID들 조회
    const chunks = await new Promise<RecordingChunk[]>((resolve, reject) => {
      const transaction = db.transaction([CHUNKS_STORE], 'readonly');
      const store = transaction.objectStore(CHUNKS_STORE);
      const index = store.index('recordingId');
      const request = index.getAll(recordingId);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result || []);
    });

    // 메타데이터와 청크들 삭제
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([METADATA_STORE, CHUNKS_STORE], 'readwrite');
      const metadataStore = transaction.objectStore(METADATA_STORE);
      const chunksStore = transaction.objectStore(CHUNKS_STORE);

      // 메타데이터 삭제
      metadataStore.delete(recordingId);

      // 청크들 삭제
      chunks.forEach((chunk) => {
        chunksStore.delete(chunk.id);
      });

      transaction.oncomplete = () => {
        logger.log(`[RecordingStorage] Deleted recording ${recordingId} (${chunks.length} chunks)`);
        resolve();
      };

      transaction.onerror = () => {
        logger.error('[RecordingStorage] Failed to delete recording:', transaction.error);
        reject(transaction.error);
      };
    });
  }

  /**
   * 특정 회의의 모든 녹음 데이터 삭제
   */
  async deleteRecordingsByMeeting(meetingId: string): Promise<void> {
    const recordings = await this.getRecordingsByMeeting(meetingId);
    for (const recording of recordings) {
      await this.deleteRecording(recording.id);
    }
  }

  /**
   * 오래된 녹음 데이터 정리 (24시간 이상)
   */
  async cleanupOldRecordings(maxAgeMs: number = 24 * 60 * 60 * 1000): Promise<number> {
    const metadataList = await this.getAllPendingMetadata();
    const now = Date.now();
    let deletedCount = 0;

    for (const metadata of metadataList) {
      const age = now - new Date(metadata.lastUpdatedAt).getTime();
      if (age > maxAgeMs) {
        await this.deleteRecording(metadata.id);
        deletedCount++;
      }
    }

    if (deletedCount > 0) {
      logger.log(`[RecordingStorage] Cleaned up ${deletedCount} old recordings`);
    }

    return deletedCount;
  }

  /**
   * Blob 배열을 하나의 Blob으로 병합
   */
  mergeChunks(chunks: Blob[]): Blob {
    return new Blob(chunks, { type: 'audio/webm' });
  }
}

// 싱글톤 인스턴스
export const recordingStorageService = new RecordingStorageService();
