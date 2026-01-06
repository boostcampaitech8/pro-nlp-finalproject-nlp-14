import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { RecordingList } from '@/components/meeting/RecordingList';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/hooks/useAuth';
import { useTeamStore } from '@/stores/teamStore';
import type { MeetingStatus, ParticipantRole, TeamMember } from '@/types';
import { teamService } from '@/services/teamService';
import api from '@/services/api';

const STATUS_LABELS: Record<MeetingStatus, string> = {
  scheduled: 'Scheduled',
  ongoing: 'Ongoing',
  completed: 'Completed',
  in_review: 'In Review',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
};

const STATUS_COLORS: Record<MeetingStatus, string> = {
  scheduled: 'bg-blue-100 text-blue-800',
  ongoing: 'bg-green-100 text-green-800',
  completed: 'bg-gray-100 text-gray-800',
  in_review: 'bg-yellow-100 text-yellow-800',
  confirmed: 'bg-purple-100 text-purple-800',
  cancelled: 'bg-red-100 text-red-800',
};

const ROLE_LABELS: Record<ParticipantRole, string> = {
  host: 'Host',
  participant: 'Participant',
};

const ROLE_COLORS: Record<ParticipantRole, string> = {
  host: 'bg-blue-100 text-blue-800',
  participant: 'bg-gray-100 text-gray-700',
};

export function MeetingDetailPage() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const navigate = useNavigate();
  const { user, logout, isLoading: authLoading } = useAuth();
  const {
    currentMeeting,
    meetingsLoading,
    meetingError,
    fetchMeeting,
    updateMeeting,
    deleteMeeting,
    addParticipant,
    updateParticipantRole,
    removeParticipant,
  } = useTeamStore();

  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editStatus, setEditStatus] = useState<MeetingStatus>('scheduled');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // 참여자 관리 상태
  const [showAddParticipantForm, setShowAddParticipantForm] = useState(false);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [participantRole, setParticipantRole] = useState<ParticipantRole>('participant');
  const [adding, setAdding] = useState(false);
  const [editingParticipantId, setEditingParticipantId] = useState<string | null>(null);
  const [editParticipantRole, setEditParticipantRole] = useState<ParticipantRole>('participant');

  // 회의 시작/참여 상태
  const [starting, setStarting] = useState(false);
  const [ending, setEnding] = useState(false);

  useEffect(() => {
    if (meetingId) {
      fetchMeeting(meetingId);
    }
  }, [meetingId, fetchMeeting]);

  useEffect(() => {
    if (currentMeeting) {
      setEditTitle(currentMeeting.title);
      setEditDescription(currentMeeting.description || '');
      setEditStatus(currentMeeting.status as MeetingStatus);

      // 팀 멤버 목록 로드
      teamService.listMembers(currentMeeting.teamId).then(setTeamMembers).catch(() => {});
    }
  }, [currentMeeting]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!meetingId || !editTitle.trim()) return;

    setSaving(true);
    try {
      await updateMeeting(meetingId, {
        title: editTitle.trim(),
        description: editDescription.trim() || null,
        status: editStatus,
      });
      setIsEditing(false);
      // 다시 fetch해서 최신 데이터 가져오기
      fetchMeeting(meetingId);
    } catch {
      // 에러는 스토어에서 처리
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!meetingId || !currentMeeting) return;
    if (!confirm('Are you sure you want to delete this meeting?')) return;

    setDeleting(true);
    try {
      await deleteMeeting(meetingId);
      navigate(`/teams/${currentMeeting.teamId}`);
    } catch {
      // 에러는 스토어에서 처리
    } finally {
      setDeleting(false);
    }
  };

  const handleAddParticipant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUserId || !meetingId) return;

    setAdding(true);
    try {
      await addParticipant(meetingId, { userId: selectedUserId, role: participantRole });
      setSelectedUserId('');
      setParticipantRole('participant');
      setShowAddParticipantForm(false);
    } catch {
      // 에러는 스토어에서 처리
    } finally {
      setAdding(false);
    }
  };

  const handleUpdateParticipantRole = async (userId: string) => {
    if (!meetingId) return;

    try {
      await updateParticipantRole(meetingId, userId, { role: editParticipantRole });
      setEditingParticipantId(null);
    } catch {
      // 에러는 스토어에서 처리
    }
  };

  const handleRemoveParticipant = async (userId: string, participantName: string) => {
    if (!meetingId) return;
    if (!confirm(`Are you sure you want to remove ${participantName} from this meeting?`)) return;

    try {
      await removeParticipant(meetingId, userId);
    } catch {
      // 에러는 스토어에서 처리
    }
  };

  // 회의 시작 (host만)
  const handleStartMeeting = async () => {
    if (!meetingId) return;

    setStarting(true);
    try {
      await api.post(`/meetings/${meetingId}/start`);
      // 회의 정보 다시 로드
      await fetchMeeting(meetingId);
      // 회의실로 이동
      navigate(`/meetings/${meetingId}/room`);
    } catch (error) {
      console.error('Failed to start meeting:', error);
      alert('회의를 시작할 수 없습니다.');
    } finally {
      setStarting(false);
    }
  };

  // 회의 종료 (host만)
  const handleEndMeeting = async () => {
    if (!meetingId) return;
    if (!confirm('회의를 종료하시겠습니까?')) return;

    setEnding(true);
    try {
      await api.post(`/meetings/${meetingId}/end`);
      // 회의 정보 다시 로드
      await fetchMeeting(meetingId);
    } catch (error) {
      console.error('Failed to end meeting:', error);
      alert('회의를 종료할 수 없습니다.');
    } finally {
      setEnding(false);
    }
  };

  // 회의 참여 (ongoing 상태일 때)
  const handleJoinMeeting = () => {
    if (!meetingId) return;
    navigate(`/meetings/${meetingId}/room`);
  };

  const currentUserParticipant = currentMeeting?.participants.find(
    (p) => p.userId === user?.id
  );
  const isHost = currentUserParticipant?.role === 'host';

  // 아직 참여자가 아닌 팀 멤버들
  const availableMembers = teamMembers.filter(
    (member) => !currentMeeting?.participants.some((p) => p.userId === member.userId)
  );

  if (meetingsLoading && !currentMeeting) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading meeting...</p>
      </div>
    );
  }

  if (meetingError && !currentMeeting) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{meetingError}</p>
          <Link to="/" className="text-blue-600 hover:underline">
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {currentMeeting && (
              <Link
                to={`/teams/${currentMeeting.teamId}`}
                className="text-gray-500 hover:text-gray-700"
              >
                &larr; Back to Team
              </Link>
            )}
            <h1 className="text-xl font-bold text-gray-900">
              {currentMeeting?.title || 'Meeting'}
            </h1>
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <span className="text-gray-600">
                Hello, <strong>{user.name}</strong>
              </span>
            )}
            <Button variant="outline" onClick={logout} isLoading={authLoading}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* 에러 메시지 */}
        {meetingError && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6">
            {meetingError}
          </div>
        )}

        {/* 회의 정보 */}
        {currentMeeting && (
          <div className="bg-white rounded-xl shadow-md p-6 mb-6">
            {isEditing ? (
              <form onSubmit={handleSave} className="space-y-4">
                <Input
                  label="Title"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  required
                />
                <Input
                  label="Description"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Status
                  </label>
                  <select
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value as MeetingStatus)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {Object.entries(STATUS_LABELS).map(([value, label]) => (
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
                    onClick={() => setIsEditing(false)}
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
                      {currentMeeting.title}
                    </h2>
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                        STATUS_COLORS[currentMeeting.status as MeetingStatus]
                      }`}
                    >
                      {STATUS_LABELS[currentMeeting.status as MeetingStatus]}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {/* 회의 시작/참여/종료 버튼 */}
                    {currentMeeting.status === 'scheduled' && isHost && (
                      <Button onClick={handleStartMeeting} isLoading={starting}>
                        Start Meeting
                      </Button>
                    )}
                    {currentMeeting.status === 'ongoing' && currentUserParticipant && (
                      <Button onClick={handleJoinMeeting}>
                        Join Meeting
                      </Button>
                    )}
                    {currentMeeting.status === 'ongoing' && isHost && (
                      <Button
                        variant="outline"
                        onClick={handleEndMeeting}
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
                          onClick={handleDelete}
                          isLoading={deleting}
                          className="text-red-600 border-red-300 hover:bg-red-50"
                        >
                          Delete
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {currentMeeting.description && (
                  <p className="text-gray-600 mb-4">{currentMeeting.description}</p>
                )}

                <div className="grid grid-cols-2 gap-4 text-sm text-gray-500">
                  {currentMeeting.scheduledAt && (
                    <div>
                      <span className="font-medium">Scheduled:</span>{' '}
                      {new Date(currentMeeting.scheduledAt).toLocaleString()}
                    </div>
                  )}
                  {currentMeeting.startedAt && (
                    <div>
                      <span className="font-medium">Started:</span>{' '}
                      {new Date(currentMeeting.startedAt).toLocaleString()}
                    </div>
                  )}
                  {currentMeeting.endedAt && (
                    <div>
                      <span className="font-medium">Ended:</span>{' '}
                      {new Date(currentMeeting.endedAt).toLocaleString()}
                    </div>
                  )}
                  <div>
                    <span className="font-medium">Created:</span>{' '}
                    {new Date(currentMeeting.createdAt).toLocaleString()}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* 참여자 섹션 */}
        {currentMeeting && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-900">
                Participants ({currentMeeting.participants.length})
              </h3>
              {isHost && availableMembers.length > 0 && (
                <Button onClick={() => setShowAddParticipantForm(!showAddParticipantForm)}>
                  {showAddParticipantForm ? 'Cancel' : 'Add Participant'}
                </Button>
              )}
            </div>

            {/* 참여자 추가 폼 */}
            {showAddParticipantForm && (
              <div className="bg-white rounded-xl shadow-md p-6 mb-4">
                <h4 className="text-lg font-semibold mb-4">Add Participant</h4>
                <form onSubmit={handleAddParticipant} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Team Member
                    </label>
                    <select
                      value={selectedUserId}
                      onChange={(e) => setSelectedUserId(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      required
                    >
                      <option value="">Select a member</option>
                      {availableMembers.map((member) => (
                        <option key={member.userId} value={member.userId}>
                          {member.user?.name || member.user?.email}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Role
                    </label>
                    <select
                      value={participantRole}
                      onChange={(e) => setParticipantRole(e.target.value as ParticipantRole)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="participant">Participant</option>
                      <option value="host">Host</option>
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" isLoading={adding}>
                      Add
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowAddParticipantForm(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              </div>
            )}

            <div className="bg-white rounded-xl shadow-md divide-y">
              {currentMeeting.participants.map((participant) => (
                <div
                  key={participant.id}
                  className="p-4 flex items-center justify-between"
                >
                  <div>
                    <p className="font-medium text-gray-900">
                      {participant.user?.name || 'Unknown User'}
                      {participant.userId === user?.id && (
                        <span className="text-gray-500 text-sm ml-2">(You)</span>
                      )}
                    </p>
                    <p className="text-sm text-gray-500">
                      {participant.user?.email}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {editingParticipantId === participant.userId ? (
                      // 역할 수정 모드
                      <>
                        <select
                          value={editParticipantRole}
                          onChange={(e) =>
                            setEditParticipantRole(e.target.value as ParticipantRole)
                          }
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="participant">Participant</option>
                          <option value="host">Host</option>
                        </select>
                        <Button
                          variant="outline"
                          onClick={() => handleUpdateParticipantRole(participant.userId)}
                          className="text-sm px-2 py-1"
                        >
                          Save
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => setEditingParticipantId(null)}
                          className="text-sm px-2 py-1"
                        >
                          Cancel
                        </Button>
                      </>
                    ) : (
                      // 일반 표시 모드
                      <>
                        <span
                          className={`px-3 py-1 rounded-full text-sm font-medium ${
                            ROLE_COLORS[participant.role as ParticipantRole]
                          }`}
                        >
                          {ROLE_LABELS[participant.role as ParticipantRole]}
                        </span>
                        {/* host는 다른 참여자의 역할 변경 가능 */}
                        {isHost && participant.userId !== user?.id && (
                          <Button
                            variant="outline"
                            onClick={() => {
                              setEditingParticipantId(participant.userId);
                              setEditParticipantRole(participant.role as ParticipantRole);
                            }}
                            className="text-sm px-2 py-1"
                          >
                            Edit
                          </Button>
                        )}
                        {/* host는 다른 참여자 삭제 가능, 본인은 삭제 가능 */}
                        {((isHost && participant.userId !== user?.id) ||
                          participant.userId === user?.id) && (
                          <Button
                            variant="outline"
                            onClick={() =>
                              handleRemoveParticipant(
                                participant.userId,
                                participant.user?.name || 'this participant'
                              )
                            }
                            className="text-sm px-2 py-1 text-red-600 border-red-300 hover:bg-red-50"
                          >
                            {participant.userId === user?.id ? 'Leave' : 'Remove'}
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 녹음 섹션 - 회의가 진행됐거나 완료된 경우에만 표시 */}
        {currentMeeting && currentMeeting.status !== 'scheduled' && (
          <div className="mt-8">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Recordings
            </h3>
            <RecordingList meetingId={currentMeeting.id} />
          </div>
        )}

        {/* Phase 2 안내 */}
        <div className="mt-8 bg-blue-50 rounded-xl p-6 text-center">
          <h4 className="text-lg font-semibold text-blue-900 mb-2">
            Coming Soon: Meeting Review
          </h4>
          <p className="text-blue-700">
            In Phase 2, you'll be able to review meeting transcripts, add comments,
            and confirm Ground Truth for your organization.
          </p>
        </div>
      </main>
    </div>
  );
}
