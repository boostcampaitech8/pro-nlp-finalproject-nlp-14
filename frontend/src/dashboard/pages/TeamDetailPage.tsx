/**
 * 팀 상세 페이지
 * 팀 정보, 회의 목록, 멤버 관리
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Home } from 'lucide-react';

import { MeetingListSection } from '@/components/team/MeetingListSection';
import { TeamInfoCard } from '@/components/team/TeamInfoCard';
import { TeamMemberSection } from '@/components/team/TeamMemberSection';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { useTeamStore } from '@/stores/teamStore';
import type { TeamRole } from '@/types';

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

  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (teamId) {
      fetchTeam(teamId);
      fetchMeetings(teamId);
    }
  }, [teamId, fetchTeam, fetchMeetings]);

  // 팀 삭제
  const handleDeleteTeam = async () => {
    if (!teamId || !confirm('Are you sure you want to delete this team?')) return;

    setDeleting(true);
    try {
      await deleteTeam(teamId);
      navigate('/dashboard');
    } finally {
      setDeleting(false);
    }
  };

  // 회의 생성
  const handleCreateMeeting = async (data: {
    title: string;
    description?: string;
    scheduledAt?: string;
  }) => {
    if (!teamId) return;
    await createMeeting(teamId, data);
  };

  // 멤버 초대
  const handleInviteMember = async (email: string, role: TeamRole) => {
    if (!teamId) return;
    await inviteMember(teamId, { email, role });
  };

  // 멤버 역할 변경
  const handleUpdateMemberRole = async (userId: string, role: TeamRole) => {
    if (!teamId) return;
    await updateMemberRole(teamId, userId, { role });
  };

  // 멤버 제거
  const handleRemoveMember = async (userId: string, memberName: string) => {
    if (!teamId) return;
    if (!confirm(`Are you sure you want to remove ${memberName} from the team?`)) return;
    await removeMember(teamId, userId);
  };

  const currentUserRole = currentTeam?.members.find(
    (m) => m.userId === user?.id
  )?.role as TeamRole | undefined;

  const isOwner = currentUserRole === 'owner';
  const isAdmin = currentUserRole === 'admin';
  const canManageMembers = isOwner || isAdmin;

  if (teamsLoading && !currentTeam) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <p className="text-white/50">Loading team...</p>
      </div>
    );
  }

  if (teamError && !currentTeam) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{teamError}</p>
          <Link to="/dashboard" className="text-mit-primary hover:underline">
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen gradient-bg">
      <header className="glass-sidebar border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
              title="Home"
            >
              <Home className="w-4 h-4" />
            </Link>
            <Link
              to="/dashboard"
              className="flex items-center gap-1 text-white/60 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm">Dashboard</span>
            </Link>
            <span className="text-white/20">|</span>
            <h1 className="text-xl font-bold text-white">
              {currentTeam?.name || 'Team'}
            </h1>
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <span className="text-white/70">
                Hello, <strong className="text-white">{user.name}</strong>
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
          <TeamInfoCard
            team={currentTeam}
            currentUserRole={currentUserRole}
            isOwner={isOwner}
            deleting={deleting}
            onDelete={handleDeleteTeam}
          />
        )}

        {/* 회의 섹션 */}
        <MeetingListSection
          meetings={meetings}
          meetingsLoading={meetingsLoading}
          meetingError={meetingError}
          onCreate={handleCreateMeeting}
        />

        {/* 팀 멤버 섹션 */}
        {currentTeam && (
          <TeamMemberSection
            members={currentTeam.members}
            currentUserId={user?.id}
            isOwner={isOwner}
            canManageMembers={canManageMembers}
            onInvite={handleInviteMember}
            onUpdateRole={handleUpdateMemberRole}
            onRemove={handleRemoveMember}
          />
        )}
      </main>
    </div>
  );
}
