import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { RECORDING_STATUS_COLORS, RECORDING_STATUS_LABELS } from '@/constants';
import { recordingService } from '@/services/recordingService';
import type { Recording } from '@/types';

interface RecordingListProps {
  meetingId: string;
}

function formatDuration(ms: number | null | undefined): string {
  if (!ms) return '-';
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function RecordingList({ meetingId }: RecordingListProps) {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  useEffect(() => {
    const fetchRecordings = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await recordingService.listRecordings(meetingId);
        setRecordings(response.items);
      } catch (err) {
        setError('녹음 파일을 불러올 수 없습니다.');
        console.error('Failed to load recordings:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchRecordings();
  }, [meetingId]);

  const handleDownload = async (recordingId: string, recording: Recording) => {
    try {
      setDownloadingId(recordingId);
      const blob = await recordingService.downloadFile(meetingId, recordingId);

      // Blob URL 생성 후 다운로드
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const displayName = recording.userId ? (recording.userName || 'unknown') : 'server';
      link.download = `recording_${displayName}.webm`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download recording:', err);
      alert('녹음 파일 다운로드에 실패했습니다.');
    } finally {
      setDownloadingId(null);
    }
  };

  const handleTranscriptDownload = (recording: Recording) => {
    if (!recording.transcriptText) return;

    const blob = new Blob([recording.transcriptText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const displayName = recording.userId ? (recording.userName || 'unknown') : 'server';
    link.download = `transcript_${displayName}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="glass-card p-6">
        <p className="text-white/50 text-center">Loading recordings...</p>
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

  if (recordings.length === 0) {
    return (
      <div className="glass-card p-6">
        <p className="text-white/50 text-center">No recordings available</p>
      </div>
    );
  }

  return (
    <div className="glass-card divide-y divide-white/10">
      {recordings.map((recording) => (
        <div
          key={recording.id}
          className="p-4 flex items-center justify-between"
        >
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <p className="font-medium text-white">
                {recording.userId ? (recording.userName || 'Unknown User') : 'Server Recording'}
              </p>
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  RECORDING_STATUS_COLORS[recording.status]
                }`}
              >
                {RECORDING_STATUS_LABELS[recording.status]}
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm text-white/60">
              <span>
                {new Date(recording.startedAt).toLocaleString()}
              </span>
              <span>
                Duration: {formatDuration(recording.durationMs)}
              </span>
              <span>
                Size: {formatFileSize(recording.fileSizeBytes)}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 ml-4">
            {(recording.status === 'completed' || recording.status === 'transcribed') && (
              <Button
                variant="outline"
                onClick={() => handleDownload(recording.id, recording)}
                isLoading={downloadingId === recording.id}
              >
                Audio
              </Button>
            )}
            {recording.status === 'transcribed' && recording.transcriptText && (
              <Button
                variant="outline"
                onClick={() => handleTranscriptDownload(recording)}
              >
                Transcript
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
