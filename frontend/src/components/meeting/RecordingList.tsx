import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { recordingService } from '@/services/recordingService';
import type { Recording, RecordingStatus } from '@/types';

interface RecordingListProps {
  meetingId: string;
}

const STATUS_LABELS: Record<RecordingStatus, string> = {
  recording: 'Recording',
  completed: 'Completed',
  failed: 'Failed',
};

const STATUS_COLORS: Record<RecordingStatus, string> = {
  recording: 'bg-red-100 text-red-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-gray-100 text-gray-600',
};

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
        setRecordings(response.recordings);
      } catch (err) {
        setError('Failed to load recordings');
        console.error('Failed to load recordings:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchRecordings();
  }, [meetingId]);

  const handleDownload = async (recordingId: string, userName: string | null | undefined) => {
    try {
      setDownloadingId(recordingId);
      const blob = await recordingService.downloadFile(meetingId, recordingId);

      // Blob URL 생성 후 다운로드
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `recording_${userName || 'unknown'}.webm`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download recording:', err);
      alert('Failed to download recording');
    } finally {
      setDownloadingId(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-md p-6">
        <p className="text-gray-500 text-center">Loading recordings...</p>
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

  if (recordings.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-md p-6">
        <p className="text-gray-500 text-center">No recordings available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-md divide-y">
      {recordings.map((recording) => (
        <div
          key={recording.id}
          className="p-4 flex items-center justify-between"
        >
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <p className="font-medium text-gray-900">
                {recording.userName || 'Unknown User'}
              </p>
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  STATUS_COLORS[recording.status]
                }`}
              >
                {STATUS_LABELS[recording.status]}
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-500">
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

          {recording.status === 'completed' && (
            <Button
              variant="outline"
              onClick={() => handleDownload(recording.id, recording.userName)}
              isLoading={downloadingId === recording.id}
              className="ml-4"
            >
              Download
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
