/**
 * 회의 정보 카드 컴포넌트
 * 회의 상세 정보 표시 및 편집 폼 담당
 */

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
import {
  MEETING_STATUS_COLORS,
  MEETING_STATUS_LABELS,
} from '@/constants';
import type { Meeting, MeetingStatus } from '@/types';

interface MeetingInfoCardProps {
  meeting: Meeting;
  isHost: boolean;
  isParticipant: boolean;
  starting: boolean;
  ending: boolean;
  onStartMeeting: () => void;
  onEndMeeting: () => void;
  onJoinMeeting: () => void;
  onSave: (data: { title: string; description: string | null; status: MeetingStatus }) => Promise<void>;
  onDelete: () => void;
  deleting: boolean;
}

export function MeetingInfoCard({
  meeting,
  isHost,
  isParticipant,
  starting,
  ending,
  onStartMeeting,
  onEndMeeting,
  onJoinMeeting,
  onSave,
  onDelete,
  deleting,
}: MeetingInfoCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(meeting.title);
  const [editDescription, setEditDescription] = useState(meeting.description || '');
  const [editStatus, setEditStatus] = useState<MeetingStatus>(meeting.status as MeetingStatus);
  const [saving, setSaving] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTitle.trim()) return;

    setSaving(true);
    try {
      await onSave({
        title: editTitle.trim(),
        description: editDescription.trim() || null,
        status: editStatus,
      });
      setIsEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditTitle(meeting.title);
    setEditDescription(meeting.description || '');
    setEditStatus(meeting.status as MeetingStatus);
    setIsEditing(false);
  };

  return (
    <div className="bg-white rounded-xl shadow-md p-6 mb-6">
      {isEditing ? (
        <form onSubmit={handleSave} className="space-y-4">
          <Input
            label="Title"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            required
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="회의 설명 (Shift+Enter: 줄바꿈)"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value as MeetingStatus)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {Object.entries(MEETING_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <Button type="submit" isLoading={saving}>
              Save
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleCancelEdit}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <>
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                {meeting.title}
              </h2>
              <span
                className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                  MEETING_STATUS_COLORS[meeting.status as MeetingStatus]
                }`}
              >
                {MEETING_STATUS_LABELS[meeting.status as MeetingStatus]}
              </span>
            </div>
            <div className="flex gap-2">
              {/* 회의 시작/참여/종료 버튼 */}
              {meeting.status === 'scheduled' && isHost && (
                <Button onClick={onStartMeeting} isLoading={starting}>
                  Start Meeting
                </Button>
              )}
              {meeting.status === 'ongoing' && isParticipant && (
                <Button onClick={onJoinMeeting}>
                  Join Meeting
                </Button>
              )}
              {meeting.status === 'ongoing' && isHost && (
                <Button
                  variant="outline"
                  onClick={onEndMeeting}
                  isLoading={ending}
                  className="text-orange-600 border-orange-300 hover:bg-orange-50"
                >
                  End Meeting
                </Button>
              )}
              {/* Edit/Delete 버튼 (host만) */}
              {isHost && (
                <>
                  <Button variant="outline" onClick={() => setIsEditing(true)}>
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    onClick={onDelete}
                    isLoading={deleting}
                    className="text-red-600 border-red-300 hover:bg-red-50"
                  >
                    Delete
                  </Button>
                </>
              )}
            </div>
          </div>

          {meeting.description && (
            <MarkdownRenderer content={meeting.description} className="text-gray-600 mb-4" />
          )}

          <div className="grid grid-cols-2 gap-4 text-sm text-gray-500">
            {meeting.scheduledAt && (
              <div>
                <span className="font-medium">Scheduled:</span>{' '}
                {new Date(meeting.scheduledAt).toLocaleString()}
              </div>
            )}
            {meeting.startedAt && (
              <div>
                <span className="font-medium">Started:</span>{' '}
                {new Date(meeting.startedAt).toLocaleString()}
              </div>
            )}
            {meeting.endedAt && (
              <div>
                <span className="font-medium">Ended:</span>{' '}
                {new Date(meeting.endedAt).toLocaleString()}
              </div>
            )}
            <div>
              <span className="font-medium">Created:</span>{' '}
              {new Date(meeting.createdAt).toLocaleString()}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
