/**
 * 회의록(트랜스크립트) 섹션 컴포넌트
 * 회의 종료 후 DB에 저장된 발화 목록을 시간순으로 표시
 */

import { useEffect, useState, useCallback } from 'react';

import { transcriptService } from '@/services/transcriptService';
import type { GetMeetingTranscriptsResponse } from '@/types';

interface TranscriptSectionProps {
  meetingId: string;
}

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

export function TranscriptSection({ meetingId }: TranscriptSectionProps) {
  const [transcript, setTranscript] = useState<GetMeetingTranscriptsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTranscript = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await transcriptService.getTranscript(meetingId);
      setTranscript(data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number } };
        if (axiosError.response?.status === 404) {
          setTranscript(null);
          return;
        }
      }
      setError('스크립트를 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  }, [meetingId]);

  useEffect(() => {
    fetchTranscript();
  }, [fetchTranscript]);

  if (loading) {
    return (
      <div className="glass-card p-6">
        <p className="text-white/50 text-center">Loading transcript...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-6">
        <p className="text-red-400 text-center">{error}</p>
      </div>
    );
  }

  if (!transcript || !transcript.utterances || transcript.utterances.length === 0) {
    return (
      <div className="glass-card p-6">
        <p className="text-white/50 text-center">No transcript available yet.</p>
      </div>
    );
  }

  return (
    <div className="glass-card">
      {/* 헤더 - 메타데이터 */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          {transcript.totalDurationMs != null && transcript.totalDurationMs > 0 && (
            <span className="text-sm text-white/60">
              Duration: {formatDuration(transcript.totalDurationMs)}
            </span>
          )}
          {transcript.speakerCount != null && transcript.speakerCount > 0 && (
            <span className="text-sm text-white/60">
              Speakers: {transcript.speakerCount}
            </span>
          )}
          <span className="text-sm text-white/40">
            {transcript.utterances.length} utterances
          </span>
        </div>

      </div>

      {/* 발화 목록 - 스크롤 가능 */}
      <div className="p-4 max-h-[500px] overflow-y-auto space-y-3">
        {transcript.utterances.map((utterance) => (
          <div key={utterance.id} className="flex gap-3">
            <div className="flex-shrink-0 w-20">
              <span className="text-xs text-white/40">
                {formatTimestamp(utterance.timestamp)}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <span className="font-medium text-mit-primary mr-2">
                [{utterance.speakerName}]
              </span>
              <span className="text-white/80">{utterance.text}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
