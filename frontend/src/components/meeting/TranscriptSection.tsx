/**
 * 회의록(트랜스크립트) 섹션 컴포넌트
 * STT 상태 표시, 회의록 내용 표시, 다운로드 기능
 */

import { useEffect, useState, useCallback } from 'react';

import { Button } from '@/components/ui/Button';
import { transcriptService } from '@/services/transcriptService';
import type {
  MeetingTranscript,
  TranscriptStatusResponse,
} from '@/types';

interface TranscriptSectionProps {
  meetingId: string;
  meetingStatus: string;
}

// 상태별 스타일
const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

// 상태별 라벨
const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  processing: 'Processing...',
  completed: 'Completed',
  failed: 'Failed',
};

function formatDuration(ms: number | null | undefined): string {
  if (!ms) return '-';
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function formatTimestamp(timestamp: string | null | undefined): string {
  if (!timestamp) return '-';
  const date = new Date(timestamp);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}

export function TranscriptSection({ meetingId, meetingStatus }: TranscriptSectionProps) {
  const [status, setStatus] = useState<TranscriptStatusResponse | null>(null);
  const [transcript, setTranscript] = useState<MeetingTranscript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // 상태 조회
  const fetchStatus = useCallback(async () => {
    try {
      const statusData = await transcriptService.getTranscriptionStatus(meetingId);
      setStatus(statusData);
      return statusData;
    } catch (err: unknown) {
      // 404, 500 등은 아직 트랜스크립트가 없는 경우로 처리
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number } };
        if (axiosError.response?.status === 404 || axiosError.response?.status === 500) {
          setStatus(null);
          return null;
        }
      }
      throw err;
    }
  }, [meetingId]);

  // 트랜스크립트 조회
  const fetchTranscript = useCallback(async () => {
    try {
      const data = await transcriptService.getTranscript(meetingId);
      setTranscript(data);
    } catch (err: unknown) {
      // 404, 500 등은 아직 트랜스크립트가 없는 경우로 처리
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number } };
        if (axiosError.response?.status === 404 || axiosError.response?.status === 500) {
          setTranscript(null);
          return;
        }
      }
      throw err;
    }
  }, [meetingId]);

  // 초기 로딩 및 폴링
  useEffect(() => {
    let intervalId: number | null = null;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const statusData = await fetchStatus();

        if (statusData?.status === 'completed') {
          await fetchTranscript();
        }
      } catch {
        // fetchStatus와 fetchTranscript에서 처리되지 않은 에러만 여기 도달
        // 대부분 네트워크 에러 등
        setStatus(null);
        setTranscript(null);
      } finally {
        setLoading(false);
      }
    };

    load();

    // processing 상태일 때 폴링
    if (status?.status === 'processing' || status?.status === 'pending') {
      intervalId = setInterval(async () => {
        const statusData = await fetchStatus();
        if (statusData?.status === 'completed') {
          await fetchTranscript();
          if (intervalId) clearInterval(intervalId);
        } else if (statusData?.status === 'failed') {
          if (intervalId) clearInterval(intervalId);
        }
      }, 5000); // 5초마다 폴링
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [meetingId, status?.status, fetchStatus, fetchTranscript]);

  // 다운로드
  const handleDownload = async () => {
    try {
      setDownloading(true);
      await transcriptService.downloadTranscript(meetingId);
    } catch (err) {
      console.error('Failed to download transcript:', err);
      alert('Failed to download transcript');
    } finally {
      setDownloading(false);
    }
  };

  // STT 시작
  const handleStartTranscription = async () => {
    try {
      setLoading(true);
      await transcriptService.startTranscription(meetingId);
      await fetchStatus();
    } catch (err) {
      console.error('Failed to start transcription:', err);
      alert('Failed to start transcription');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !status && !transcript) {
    return (
      <div className="bg-white rounded-xl shadow-md p-6">
        <p className="text-gray-500 text-center">Loading transcript...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl shadow-md p-6">
        <p className="text-red-600 text-center">{error}</p>
      </div>
    );
  }

  // 트랜스크립트가 없는 경우
  if (!status && !transcript) {
    return (
      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="text-center">
          <p className="text-gray-500 mb-4">No transcript available yet.</p>
          {meetingStatus === 'completed' && (
            <Button onClick={handleStartTranscription} isLoading={loading}>
              Start Transcription
            </Button>
          )}
          {meetingStatus === 'ongoing' && (
            <p className="text-sm text-gray-400">
              Transcription will start automatically when the meeting ends.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-md">
      {/* 헤더 */}
      <div className="p-4 border-b flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              STATUS_STYLES[status?.status || transcript?.status || 'pending']
            }`}
          >
            {STATUS_LABELS[status?.status || transcript?.status || 'pending']}
          </span>

          {status && status.status === 'processing' && (
            <span className="text-sm text-gray-500">
              Processing: {status.processedRecordings} / {status.totalRecordings} recordings
            </span>
          )}

          {transcript?.totalDurationMs && (
            <span className="text-sm text-gray-500">
              Duration: {formatDuration(transcript.totalDurationMs)}
            </span>
          )}

          {transcript?.speakerCount && (
            <span className="text-sm text-gray-500">
              Speakers: {transcript.speakerCount}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {(status?.status === 'completed' || transcript?.status === 'completed') && (
            <Button
              variant="outline"
              onClick={handleDownload}
              isLoading={downloading}
            >
              Download JSON
            </Button>
          )}
        </div>
      </div>

      {/* 에러 메시지 */}
      {(status?.error || transcript?.error) && (
        <div className="p-4 bg-red-50 text-red-700 text-sm">
          Error: {status?.error || transcript?.error}
        </div>
      )}

      {/* 트랜스크립트 내용 */}
      {transcript?.utterances && transcript.utterances.length > 0 && (
        <div className="p-4">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full text-left mb-4 flex items-center justify-between text-gray-700 hover:text-gray-900"
          >
            <span className="font-medium">
              Transcript ({transcript.utterances.length} utterances)
            </span>
            <span className="text-sm">
              {expanded ? 'Collapse' : 'Expand'}
            </span>
          </button>

          {expanded && (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {transcript.utterances.map((utterance) => (
                <div key={utterance.id} className="flex gap-3">
                  <div className="flex-shrink-0 w-24">
                    <span className="text-xs text-gray-400">
                      {formatTimestamp(utterance.timestamp)}
                    </span>
                  </div>
                  <div className="flex-1">
                    <span className="font-medium text-blue-600 mr-2">
                      [{utterance.speakerName}]
                    </span>
                    <span className="text-gray-700">{utterance.text}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 전체 텍스트 (utterances가 없는 경우) */}
      {transcript?.fullText && (!transcript.utterances || transcript.utterances.length === 0) && (
        <div className="p-4">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full text-left mb-4 flex items-center justify-between text-gray-700 hover:text-gray-900"
          >
            <span className="font-medium">Full Text</span>
            <span className="text-sm">
              {expanded ? 'Collapse' : 'Expand'}
            </span>
          </button>

          {expanded && (
            <div className="prose prose-sm max-w-none max-h-96 overflow-y-auto whitespace-pre-wrap text-gray-700">
              {transcript.fullText}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
