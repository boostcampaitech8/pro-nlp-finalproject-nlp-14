/**
 * 회의 상세 페이지
 * 회의 정보, 참여자 관리, 녹음 목록 표시
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { MeetingInfoCard } from '@/components/meeting/MeetingInfoCard';
import { ParticipantSection } from '@/components/meeting/ParticipantSection';
import { RecordingList } from '@/components/meeting/RecordingList';
import { TranscriptSection } from '@/components/meeting/TranscriptSection';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { useTeamStore } from '@/stores/teamStore';
import type { MeetingStatus, ParticipantRole, TeamMember } from '@/types';
import { teamService } from '@/services/teamService';
import api from '@/services/api';

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

  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [starting, setStarting] = useState(false);
  const [ending, setEnding] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (meetingId) {
      fetchMeeting(meetingId);
    }
  }, [meetingId, fetchMeeting]);

  useEffect(() => {
    if (currentMeeting) {
      teamService.listMembers(currentMeeting.teamId).then(setTeamMembers).catch(() => {});
    }
  }, [currentMeeting]);

  // 회의 시작 (host만)
  const handleStartMeeting = async () => {
    if (!meetingId) return;

    setStarting(true);
    try {
      await api.post(`/meetings/${meetingId}/start`);
      await fetchMeeting(meetingId);
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

  // 회의 정보 저장
  const handleSaveMeeting = async (data: {
    title: string;
    description: string | null;
    status: MeetingStatus;
  }) => {
    if (!meetingId) return;
    await updateMeeting(meetingId, data);
    fetchMeeting(meetingId);
  };

  // 회의 삭제
  const handleDeleteMeeting = async () => {
    if (!meetingId || !currentMeeting) return;
    if (!confirm('Are you sure you want to delete this meeting?')) return;

    setDeleting(true);
    try {
      await deleteMeeting(meetingId);
      navigate(`/teams/${currentMeeting.teamId}`);
    } finally {
      setDeleting(false);
    }
  };

  // 참여자 추가
  const handleAddParticipant = async (userId: string, role: ParticipantRole) => {
    if (!meetingId) return;
    await addParticipant(meetingId, { userId, role });
  };

  // 참여자 역할 변경
  const handleUpdateParticipantRole = async (userId: string, role: ParticipantRole) => {
    if (!meetingId) return;
    await updateParticipantRole(meetingId, userId, { role });
  };

  // 참여자 제거
  const handleRemoveParticipant = async (userId: string, participantName: string) => {
    if (!meetingId) return;
    if (!confirm(`Are you sure you want to remove ${participantName} from this meeting?`)) return;
    await removeParticipant(meetingId, userId);
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
          <MeetingInfoCard
            meeting={currentMeeting}
            isHost={isHost}
            isParticipant={!!currentUserParticipant}
            starting={starting}
            ending={ending}
            onStartMeeting={handleStartMeeting}
            onEndMeeting={handleEndMeeting}
            onJoinMeeting={handleJoinMeeting}
            onSave={handleSaveMeeting}
            onDelete={handleDeleteMeeting}
            deleting={deleting}
          />
        )}

        {/* 참여자 섹션 */}
        {currentMeeting && (
          <ParticipantSection
            participants={currentMeeting.participants}
            availableMembers={availableMembers}
            currentUserId={user?.id}
            isHost={isHost}
            onAddParticipant={handleAddParticipant}
            onUpdateRole={handleUpdateParticipantRole}
            onRemoveParticipant={handleRemoveParticipant}
          />
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

        {/* 회의록(트랜스크립트) 섹션 - 회의가 진행됐거나 완료된 경우에만 표시 */}
        {currentMeeting && currentMeeting.status !== 'scheduled' && (
          <div className="mt-8">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Transcript
            </h3>
            <TranscriptSection
              meetingId={currentMeeting.id}
              meetingStatus={currentMeeting.status}
            />
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
