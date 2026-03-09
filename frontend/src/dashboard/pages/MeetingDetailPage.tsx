/**
 * 회의 상세 페이지
 * 회의 정보, 참여자 관리, 녹음 목록 표시
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Home } from 'lucide-react';

import { MeetingInfoCard } from '@/components/meeting/MeetingInfoCard';
import { ParticipantSection } from '@/components/meeting/ParticipantSection';
import { TranscriptSection } from '@/components/meeting/TranscriptSection';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { useTeamStore } from '@/stores/teamStore';
import type { MeetingStatus, ParticipantRole, TeamMember } from '@/types';
import { teamService } from '@/services/teamService';
import { kgService } from '@/services/kgService';
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
  const [minutesStatus, setMinutesStatus] = useState<
    'loading' | 'not_started' | 'generating' | 'completed' | 'failed'
  >('loading');

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

  // 회의록 상태 초기 확인 (마운트 시 + 미팅 상태 변경 시 1회)
  useEffect(() => {
    if (!currentMeeting || currentMeeting.status === 'scheduled') return;

    let cancelled = false;
    setMinutesStatus('loading');

    kgService.getMinutesStatus(currentMeeting.id)
      .then((status) => { if (!cancelled) setMinutesStatus(status); })
      .catch(() => { if (!cancelled) setMinutesStatus('not_started'); });

    return () => { cancelled = true; };
  }, [currentMeeting?.id, currentMeeting?.status]);

  // generating이거나 ongoing(room_finished 대기)일 때만 폴링
  useEffect(() => {
    const shouldPoll =
      minutesStatus === 'generating' ||
      (currentMeeting?.status === 'ongoing' && minutesStatus !== 'completed' && minutesStatus !== 'failed');
    if (!shouldPoll || !currentMeeting || !meetingId) return;

    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const poll = async () => {
      try {
        // ongoing → completed 전환 감지용
        if (currentMeeting.status === 'ongoing') fetchMeeting(meetingId);

        const status = await kgService.getMinutesStatus(currentMeeting.id);
        if (cancelled) return;
        setMinutesStatus(status);

        if (status === 'generating' || status === 'not_started') {
          timeoutId = setTimeout(poll, 5000);
        }
      } catch {
        if (!cancelled) setMinutesStatus('not_started');
      }
    };

    timeoutId = setTimeout(poll, 5000);

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [minutesStatus, currentMeeting?.id, currentMeeting?.status]);

  // 회의 시작 (host만)
  const handleStartMeeting = async () => {
    if (!meetingId) return;

    setStarting(true);
    try {
      await api.post(`/meetings/${meetingId}/start`);
      await fetchMeeting(meetingId);
      navigate(`/dashboard/meetings/${meetingId}/room`);
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
    navigate(`/dashboard/meetings/${meetingId}/room`);
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
    if (!confirm('이 회의를 삭제하시겠습니까?')) return;

    setDeleting(true);
    try {
      await deleteMeeting(meetingId);
      navigate(`/dashboard/teams/${currentMeeting.teamId}`);
    } finally {
      setDeleting(false);
    }
  };

  // 참여자 추가
  const handleAddParticipant = async (userId: string, role: ParticipantRole) => {
    if (!meetingId) return;
    await addParticipant(meetingId, { userId, role });
  };

  // 참여자 역할 수정
  const handleUpdateRole = async (userId: string, role: ParticipantRole) => {
    if (!meetingId) return;
    await updateParticipantRole(meetingId, userId, { role });
  };

  // 참여자 제거
  const handleRemoveParticipant = async (userId: string, name: string) => {
    if (!meetingId) return;
    if (!confirm(`${name}님을 회의에서 제거하시겠습니까?`)) return;
    await removeParticipant(meetingId, userId);
  };

  // PR 생성 요청
  const handleGeneratePR = async () => {
    if (!meetingId) return;

    try {
      await kgService.generatePR(meetingId);
      setMinutesStatus('generating');
    } catch {
      setMinutesStatus('failed');
    }
  };

  // 회의 생성자가 host
  const isHost = currentMeeting?.createdBy === user?.id;

  // 이미 참여자인 멤버를 제외한 팀 멤버 목록
  const availableMembers = teamMembers.filter(
    (member) => !currentMeeting?.participants.some((p) => p.userId === member.userId)
  );

  if (meetingsLoading && !currentMeeting) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <p className="text-white/50">Loading meeting...</p>
      </div>
    );
  }

  if (meetingError && !currentMeeting) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{meetingError}</p>
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
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
              title="Home"
            >
              <Home className="w-4 h-4" />
            </Link>
            {currentMeeting && (
              <Link
                to={`/dashboard/teams/${currentMeeting.teamId}`}
                className="flex items-center gap-1 text-white/60 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm">Team</span>
              </Link>
            )}
            <span className="text-white/20">|</span>
            <h1 className="text-xl font-bold text-white">
              {currentMeeting?.title || 'Meeting'}
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

      <main className="max-w-4xl mx-auto px-4 pt-8 pb-24">
        {/* 에러 메시지 */}
        {meetingError && (
          <div className="bg-red-500/20 text-red-300 p-4 rounded-lg mb-6 border border-red-500/30">
            {meetingError}
          </div>
        )}

        {/* 회의 정보 */}
        {currentMeeting && (
          <MeetingInfoCard
            meeting={currentMeeting}
            isHost={isHost}
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

        {/* PR Review 섹션 - 회의가 진행됐거나 완료된 경우에만 표시 */}
        {currentMeeting && currentMeeting.status !== 'scheduled' && (
          <div className="mt-8 glass-card p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-white mb-2">
                  Meeting Review
                </h3>
                <p className="text-white/60">
                  {minutesStatus === 'generating'
                    ? '회의록을 생성하고 있습니다. 잠시만 기다려주세요...'
                    : minutesStatus === 'completed'
                    ? '회의록이 생성되었습니다. 결정사항을 리뷰할 수 있습니다.'
                    : minutesStatus === 'failed'
                    ? '저장된 회의 내용이 부족하여 안건을 추출하지 못했습니다.'
                    : '회의 트랜스크립트를 기반으로 결정사항을 생성하고 리뷰할 수 있습니다.'}
                </p>
              </div>
              <div>
                {minutesStatus === 'loading' && (
                  <Button variant="outline" disabled>
                    확인 중...
                  </Button>
                )}
                {minutesStatus === 'generating' && (
                  <Button variant="outline" disabled>
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      생성 중...
                    </span>
                  </Button>
                )}
                {minutesStatus === 'completed' && (
                  <Button
                    variant="primary"
                    onClick={() => navigate(`/dashboard/meetings/${meetingId}/minutes`)}
                  >
                    View Minutes
                  </Button>
                )}
                {minutesStatus === 'not_started' && (
                  <Button
                    variant="primary"
                    onClick={handleGeneratePR}
                  >
                    Generate PR
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 참여자 섹션 */}
        {currentMeeting && (
          <div className="mt-8">
            <ParticipantSection
              participants={currentMeeting.participants}
              availableMembers={availableMembers}
              currentUserId={user?.id}
              isHost={isHost}
              onAddParticipant={handleAddParticipant}
              onUpdateRole={handleUpdateRole}
              onRemoveParticipant={handleRemoveParticipant}
            />
          </div>
        )}

        {/* 회의록(트랜스크립트) 섹션 - 회의가 완료된 경우에만 표시 */}
        {currentMeeting && currentMeeting.status === 'completed' && (
          <div className="mt-8">
            <h3 className="text-xl font-bold text-white mb-4">
              Transcript
            </h3>
            <TranscriptSection meetingId={currentMeeting.id} />
          </div>
        )}

      </main>
    </div>
  );
}
