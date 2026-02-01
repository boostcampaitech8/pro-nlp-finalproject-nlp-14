/**
 * 회의 목록 섹션 컴포넌트
 * 회의 목록 표시 및 생성 폼
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  MEETING_STATUS_COLORS,
  MEETING_STATUS_LABELS,
} from '@/constants';
import { kgService } from '@/services/kgService';
import type { Meeting, MeetingStatus } from '@/types';

interface MeetingListSectionProps {
  meetings: Meeting[];
  meetingsLoading: boolean;
  meetingError: string | null;
  onCreate: (data: { title: string; description?: string; scheduledAt?: string }) => Promise<void>;
}

export function MeetingListSection({
  meetings,
  meetingsLoading,
  meetingError,
  onCreate,
}: MeetingListSectionProps) {
  const navigate = useNavigate();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [creating, setCreating] = useState(false);

  // 회의별 결정사항 존재 여부
  const [decisionsMap, setDecisionsMap] = useState<Record<string, boolean | null>>({});
  // 회의별 Generate PR 로딩 상태
  const [generatingMap, setGeneratingMap] = useState<Record<string, boolean>>({});

  // 진행된 회의들의 결정사항 존재 여부 확인
  useEffect(() => {
    const checkDecisions = async () => {
      const nonScheduledMeetings = meetings.filter((m) => m.status !== 'scheduled');

      for (const meeting of nonScheduledMeetings) {
        // 이미 확인된 경우 스킵
        if (decisionsMap[meeting.id] !== undefined) continue;

        // 로딩 중으로 표시
        setDecisionsMap((prev) => ({ ...prev, [meeting.id]: null }));

        try {
          const hasDecisions = await kgService.hasDecisions(meeting.id);
          setDecisionsMap((prev) => ({ ...prev, [meeting.id]: hasDecisions }));
        } catch {
          setDecisionsMap((prev) => ({ ...prev, [meeting.id]: false }));
        }
      }
    };

    if (meetings.length > 0) {
      checkDecisions();
    }
  }, [meetings]);

  // Generate PR 핸들러
  const handleGeneratePR = async (e: React.MouseEvent, meetingId: string) => {
    e.preventDefault();
    e.stopPropagation();

    setGeneratingMap((prev) => ({ ...prev, [meetingId]: true }));
    try {
      await kgService.generatePR(meetingId);
      alert('PR 생성 작업이 시작되었습니다. 잠시 후 회의록에서 확인하세요.');
    } catch (error) {
      console.error('Failed to generate PR:', error);
      alert('PR 생성에 실패했습니다.');
    } finally {
      setGeneratingMap((prev) => ({ ...prev, [meetingId]: false }));
    }
  };

  // Minutes 페이지 이동
  const handleGoToMinutes = (e: React.MouseEvent, meetingId: string) => {
    e.preventDefault();
    e.stopPropagation();
    navigate(`/dashboard/meetings/${meetingId}/minutes`);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

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
      setShowCreateForm(false);
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-gray-900">Meetings</h3>
        <Button onClick={() => setShowCreateForm(!showCreateForm)}>
          {showCreateForm ? 'Cancel' : 'Create Meeting'}
        </Button>
      </div>

      {/* 회의 생성 폼 */}
      {showCreateForm && (
        <div className="bg-white rounded-xl shadow-md p-6 mb-6">
          <h4 className="text-lg font-semibold mb-4">Create New Meeting</h4>
          <form onSubmit={handleCreate} className="space-y-4">
            <Input
              label="Meeting Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter meeting title"
              required
            />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description (optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter meeting description (Shift+Enter: new line)"
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Scheduled At (optional)
              </label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" isLoading={creating}>
                Create
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* 에러 메시지 */}
      {meetingError && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6">
          {meetingError}
        </div>
      )}

      {/* 로딩 */}
      {meetingsLoading && meetings.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          Loading meetings...
        </div>
      )}

      {/* 회의 목록 */}
      {!meetingsLoading && meetings.length === 0 ? (
        <div className="bg-white rounded-xl shadow-md p-8 text-center">
          <p className="text-gray-600 mb-4">No meetings yet.</p>
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
              className="block bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="text-lg font-semibold text-gray-900 mb-1">
                    {meeting.title}
                  </h4>
                  {meeting.description && (
                    <p className="text-gray-600 text-sm mb-2 line-clamp-2">
                      {meeting.description}
                    </p>
                  )}
                  <div className="flex items-center gap-4 text-sm text-gray-500">
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
                  {/* PR Review / Generate PR 버튼 - scheduled가 아닌 회의만 표시 */}
                  {meeting.status !== 'scheduled' && (
                    <>
                      {decisionsMap[meeting.id] === null ? (
                        <Button variant="outline" size="sm" disabled>
                          확인 중...
                        </Button>
                      ) : decisionsMap[meeting.id] ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => handleGoToMinutes(e, meeting.id)}
                        >
                          View Minutes
                        </Button>
                      ) : (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={(e) => handleGeneratePR(e, meeting.id)}
                          isLoading={generatingMap[meeting.id]}
                        >
                          Generate PR
                        </Button>
                      )}
                    </>
                  )}
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
