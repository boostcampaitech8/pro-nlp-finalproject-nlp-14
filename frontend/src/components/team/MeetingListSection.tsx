/**
 * 회의 목록 섹션 컴포넌트
 * 회의 목록 표시 및 생성 폼
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import {
  MEETING_STATUS_COLORS,
  MEETING_STATUS_LABELS,
} from '@/constants';
import { cn } from '@/lib/utils';
import type { Meeting, MeetingStatus } from '@/types';

interface MeetingListSectionProps {
  meetings: Meeting[];
  meetingsLoading: boolean;
  meetingError: string | null;
  onCreate: (data: { title: string; description?: string; scheduledAt?: string }) => Promise<void>;
}

const inputBaseClasses =
  'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-white/30 outline-none focus:border-mit-primary/50 focus:ring-2 focus:ring-mit-primary/20 transition-all';

export function MeetingListSection({
  meetings,
  meetingsLoading,
  meetingError,
  onCreate,
}: MeetingListSectionProps) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => {
    setTitle('');
    setDescription('');
    setScheduledAt('');
    setError(null);
    setShowCreateForm(false);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('회의 제목을 입력해주세요.');
      return;
    }

    setCreating(true);
    try {
      await onCreate({
        title: title.trim(),
        description: description.trim() || undefined,
        scheduledAt: scheduledAt || undefined,
      });
      setTitle('');
      setDescription('');
      setScheduledAt('');
      setError(null);
      setShowCreateForm(false);
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-white">Meetings</h3>
        <Button
          variant={showCreateForm ? 'outline' : 'primary'}
          onClick={() => showCreateForm ? handleCancel() : setShowCreateForm(true)}
        >
          {showCreateForm ? 'Cancel' : 'Create Meeting'}
        </Button>
      </div>

      {/* 회의 생성 폼 */}
      {showCreateForm && (
        <div className="glass-card p-6 mb-6">
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">
                회의 제목 <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="예: 주간 스프린트 회의"
                disabled={creating}
                className={inputBaseClasses}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">
                회의 설명
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="회의 주제나 안건을 입력하세요"
                rows={3}
                disabled={creating}
                className={cn(inputBaseClasses, 'resize-none')}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">
                예정 일시
              </label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                disabled={creating}
                className={inputBaseClasses}
              />
            </div>
            {error && (
              <div className="text-sm text-red-400 bg-red-400/10 px-3 py-2 rounded-lg">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button type="submit" isLoading={creating}>
                Create Meeting
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* 에러 메시지 */}
      {meetingError && (
        <div className="bg-red-500/20 text-red-300 p-4 rounded-lg mb-6 border border-red-500/30">
          {meetingError}
        </div>
      )}

      {/* 로딩 */}
      {meetingsLoading && meetings.length === 0 && (
        <div className="text-center py-12 text-white/50">
          Loading meetings...
        </div>
      )}

      {/* 회의 목록 */}
      {!meetingsLoading && meetings.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <p className="text-white/60 mb-4">No meetings yet.</p>
          <Button onClick={() => setShowCreateForm(true)}>
            Create First Meeting
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {meetings.map((meeting) => (
            <Link
              key={meeting.id}
              to={`/dashboard/meetings/${meeting.id}`}
              className="block glass-card-hover p-6"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="text-lg font-semibold text-white mb-1">
                    {meeting.title}
                  </h4>
                  {meeting.description && (
                    <p className="text-white/60 text-sm mb-2 line-clamp-2">
                      {meeting.description}
                    </p>
                  )}
                  <div className="flex items-center gap-4 text-sm text-white/50">
                    {meeting.scheduledAt && (
                      <span>
                        Scheduled: {new Date(meeting.scheduledAt).toLocaleString()}
                      </span>
                    )}
                    <span>
                      Created: {new Date(meeting.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3 ml-4">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap ${
                      MEETING_STATUS_COLORS[meeting.status as MeetingStatus]
                    }`}
                  >
                    {MEETING_STATUS_LABELS[meeting.status as MeetingStatus]}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
