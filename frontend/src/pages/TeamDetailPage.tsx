import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/hooks/useAuth';
import { useTeamStore } from '@/stores/teamStore';
import type { MeetingStatus, TeamRole } from '@/types';

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

const ROLE_LABELS: Record<TeamRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
};

const ROLE_COLORS: Record<TeamRole, string> = {
  owner: 'bg-purple-100 text-purple-800',
  admin: 'bg-blue-100 text-blue-800',
  member: 'bg-gray-100 text-gray-700',
};

export function TeamDetailPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const navigate = useNavigate();
  const { user, logout, isLoading: authLoading } = useAuth();
  const {
    currentTeam,
    meetings,
    teamsLoading,
    meetingsLoading,
    teamError,
    meetingError,
    fetchTeam,
    fetchMeetings,
    createMeeting,
    deleteTeam,
    inviteMember,
    updateMemberRole,
    removeMember,
  } = useTeamStore();

  const [showCreateMeetingForm, setShowCreateMeetingForm] = useState(false);
  const [newMeetingTitle, setNewMeetingTitle] = useState('');
  const [newMeetingDescription, setNewMeetingDescription] = useState('');
  const [newMeetingScheduledAt, setNewMeetingScheduledAt] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // 멤버 관리 상태
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<TeamRole>('member');
  const [inviting, setInviting] = useState(false);
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null);
  const [editMemberRole, setEditMemberRole] = useState<TeamRole>('member');

  useEffect(() => {
    if (teamId) {
      fetchTeam(teamId);
      fetchMeetings(teamId);
    }
  }, [teamId, fetchTeam, fetchMeetings]);

  const handleCreateMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMeetingTitle.trim() || !teamId) return;

    setCreating(true);
    try {
      await createMeeting(teamId, {
        title: newMeetingTitle.trim(),
        description: newMeetingDescription.trim() || undefined,
        scheduledAt: newMeetingScheduledAt || undefined,
      });
      setNewMeetingTitle('');
      setNewMeetingDescription('');
      setNewMeetingScheduledAt('');
      setShowCreateMeetingForm(false);
    } catch {
      // 에러는 스토어에서 처리
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteTeam = async () => {
    if (!teamId || !confirm('Are you sure you want to delete this team?')) return;

    setDeleting(true);
    try {
      await deleteTeam(teamId);
      navigate('/');
    } catch {
      // 에러는 스토어에서 처리
    } finally {
      setDeleting(false);
    }
  };

  const handleInviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim() || !teamId) return;

    setInviting(true);
    try {
      await inviteMember(teamId, { email: inviteEmail.trim(), role: inviteRole });
      setInviteEmail('');
      setInviteRole('member');
      setShowInviteForm(false);
    } catch {
      // 에러는 스토어에서 처리
    } finally {
      setInviting(false);
    }
  };

  const handleUpdateMemberRole = async (userId: string) => {
    if (!teamId) return;

    try {
      await updateMemberRole(teamId, userId, { role: editMemberRole });
      setEditingMemberId(null);
    } catch {
      // 에러는 스토어에서 처리
    }
  };

  const handleRemoveMember = async (userId: string, memberName: string) => {
    if (!teamId) return;
    if (!confirm(`Are you sure you want to remove ${memberName} from the team?`)) return;

    try {
      await removeMember(teamId, userId);
    } catch {
      // 에러는 스토어에서 처리
    }
  };

  const currentUserRole = currentTeam?.members.find(
    (m) => m.userId === user?.id
  )?.role;

  const isOwner = currentUserRole === 'owner';
  const isAdmin = currentUserRole === 'admin';
  const canManageMembers = isOwner || isAdmin;

  if (teamsLoading && !currentTeam) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading team...</p>
      </div>
    );
  }

  if (teamError && !currentTeam) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{teamError}</p>
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
            <Link to="/" className="text-gray-500 hover:text-gray-700">
              &larr; Back
            </Link>
            <h1 className="text-xl font-bold text-gray-900">
              {currentTeam?.name || 'Team'}
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
        {/* 팀 정보 */}
        {currentTeam && (
          <div className="bg-white rounded-xl shadow-md p-6 mb-6">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  {currentTeam.name}
                </h2>
                {currentTeam.description && (
                  <p className="text-gray-600 mb-4">{currentTeam.description}</p>
                )}
                <p className="text-sm text-gray-500">
                  {currentTeam.members.length} member(s) | Your role:{' '}
                  <span className="font-medium">{currentUserRole}</span>
                </p>
              </div>
              {isOwner && (
                <Button
                  variant="outline"
                  onClick={handleDeleteTeam}
                  isLoading={deleting}
                  className="text-red-600 border-red-300 hover:bg-red-50"
                >
                  Delete Team
                </Button>
              )}
            </div>
          </div>
        )}

        {/* 회의 섹션 */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-gray-900">Meetings</h3>
          <Button onClick={() => setShowCreateMeetingForm(!showCreateMeetingForm)}>
            {showCreateMeetingForm ? 'Cancel' : 'Create Meeting'}
          </Button>
        </div>

        {/* 회의 생성 폼 */}
        {showCreateMeetingForm && (
          <div className="bg-white rounded-xl shadow-md p-6 mb-6">
            <h4 className="text-lg font-semibold mb-4">Create New Meeting</h4>
            <form onSubmit={handleCreateMeeting} className="space-y-4">
              <Input
                label="Meeting Title"
                value={newMeetingTitle}
                onChange={(e) => setNewMeetingTitle(e.target.value)}
                placeholder="Enter meeting title"
                required
              />
              <Input
                label="Description (optional)"
                value={newMeetingDescription}
                onChange={(e) => setNewMeetingDescription(e.target.value)}
                placeholder="Enter meeting description"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Scheduled At (optional)
                </label>
                <input
                  type="datetime-local"
                  value={newMeetingScheduledAt}
                  onChange={(e) => setNewMeetingScheduledAt(e.target.value)}
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
                  onClick={() => setShowCreateMeetingForm(false)}
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
            <Button onClick={() => setShowCreateMeetingForm(true)}>
              Create First Meeting
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {meetings.map((meeting) => (
              <Link
                key={meeting.id}
                to={`/meetings/${meeting.id}`}
                className="block bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div>
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
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-medium ${
                      STATUS_COLORS[meeting.status as MeetingStatus]
                    }`}
                  >
                    {STATUS_LABELS[meeting.status as MeetingStatus]}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}

        {/* 팀 멤버 섹션 */}
        {currentTeam && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-900">
                Team Members ({currentTeam.members.length})
              </h3>
              {canManageMembers && (
                <Button onClick={() => setShowInviteForm(!showInviteForm)}>
                  {showInviteForm ? 'Cancel' : 'Invite Member'}
                </Button>
              )}
            </div>

            {/* 멤버 초대 폼 */}
            {showInviteForm && (
              <div className="bg-white rounded-xl shadow-md p-6 mb-4">
                <h4 className="text-lg font-semibold mb-4">Invite New Member</h4>
                <form onSubmit={handleInviteMember} className="space-y-4">
                  <Input
                    label="Email"
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="Enter member's email"
                    required
                  />
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Role
                    </label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as TeamRole)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" isLoading={inviting}>
                      Invite
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowInviteForm(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              </div>
            )}

            <div className="bg-white rounded-xl shadow-md divide-y">
              {currentTeam.members.map((member) => (
                <div
                  key={member.id}
                  className="p-4 flex items-center justify-between"
                >
                  <div>
                    <p className="font-medium text-gray-900">
                      {member.user?.name || 'Unknown User'}
                      {member.userId === user?.id && (
                        <span className="text-gray-500 text-sm ml-2">(You)</span>
                      )}
                    </p>
                    <p className="text-sm text-gray-500">{member.user?.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {editingMemberId === member.userId ? (
                      // 역할 수정 모드
                      <>
                        <select
                          value={editMemberRole}
                          onChange={(e) => setEditMemberRole(e.target.value as TeamRole)}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                        </select>
                        <Button
                          variant="outline"
                          onClick={() => handleUpdateMemberRole(member.userId)}
                          className="text-sm px-2 py-1"
                        >
                          Save
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => setEditingMemberId(null)}
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
                            ROLE_COLORS[member.role as TeamRole]
                          }`}
                        >
                          {ROLE_LABELS[member.role as TeamRole]}
                        </span>
                        {/* owner만 역할 변경 가능, owner 역할은 변경 불가 */}
                        {isOwner && member.role !== 'owner' && (
                          <Button
                            variant="outline"
                            onClick={() => {
                              setEditingMemberId(member.userId);
                              setEditMemberRole(member.role as TeamRole);
                            }}
                            className="text-sm px-2 py-1"
                          >
                            Edit
                          </Button>
                        )}
                        {/* owner/admin은 다른 member 삭제 가능, 본인 삭제 가능 (owner 제외) */}
                        {((canManageMembers && member.role === 'member') ||
                          (member.userId === user?.id && member.role !== 'owner')) && (
                          <Button
                            variant="outline"
                            onClick={() =>
                              handleRemoveMember(member.userId, member.user?.name || 'this member')
                            }
                            className="text-sm px-2 py-1 text-red-600 border-red-300 hover:bg-red-50"
                          >
                            Remove
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
      </main>
    </div>
  );
}
