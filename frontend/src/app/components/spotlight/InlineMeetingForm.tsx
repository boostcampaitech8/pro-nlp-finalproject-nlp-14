import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { X, ArrowRight, Loader2, Check, ChevronRight, ChevronLeft } from 'lucide-react';
import { useTeamStore } from '@/stores/teamStore';
import { teamService } from '@/services/teamService';
import { meetingService } from '@/services/meetingService';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { Button, Input } from '@/app/components/ui';
import { cn } from '@/lib/utils';
import type { TeamMember } from '@/types';

interface InlineMeetingFormProps {
  onClose: () => void;
}

type Step = 'info' | 'invite' | 'success';

const LAST_MEETING_TEAM_KEY = 'mit-last-meeting-team-id';

function getDefaultTeamId(teams: Array<{ id: string; name: string }>): string {
  if (teams.length === 0) return '';
  if (teams.length === 1) return teams[0].id;

  // 마지막으로 회의를 생성한 팀
  const lastTeamId = localStorage.getItem(LAST_MEETING_TEAM_KEY);
  if (lastTeamId && teams.some((t) => t.id === lastTeamId)) {
    return lastTeamId;
  }

  // 없으면 가나다순 첫 번째 팀
  const sorted = [...teams].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
  return sorted[0].id;
}

export function InlineMeetingForm({ onClose }: InlineMeetingFormProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { teams } = useTeamStore();

  // Step
  const [step, setStep] = useState<Step>('info');

  // Step 1: info
  const [selectedTeamId, setSelectedTeamId] = useState(() => getDefaultTeamId(teams));
  const [meetingTitle, setMeetingTitle] = useState('');
  const [meetingDescription, setMeetingDescription] = useState('');

  // Step 2: invite
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [isLoadingMembers, setIsLoadingMembers] = useState(false);
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());

  // Step 3: success
  const [createdMeetingId, setCreatedMeetingId] = useState<string | null>(null);
  const [inviteResults, setInviteResults] = useState<{ succeeded: number; failed: number }>({
    succeeded: 0,
    failed: 0,
  });

  // Shared
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canProceedToInvite = Boolean(selectedTeamId && meetingTitle.trim());

  // Load members when entering invite step
  useEffect(() => {
    if (step === 'invite' && selectedTeamId) {
      setIsLoadingMembers(true);
      setError(null);
      teamService
        .getTeam(selectedTeamId)
        .then((team) => {
          setMembers(team.members || []);
        })
        .catch(() => {
          setError('팀원 정보를 불러오지 못했어요. 잠시 후 다시 시도해주세요.');
        })
        .finally(() => {
          setIsLoadingMembers(false);
        });
    }
  }, [step, selectedTeamId]);

  const membersExcludingCurrentUser = members.filter((m) => m.userId !== user?.id);

  const allSelected =
    membersExcludingCurrentUser.length > 0 &&
    membersExcludingCurrentUser.every((m) => selectedMemberIds.has(m.userId));

  const selectedCount = selectedMemberIds.size;

  const toggleMember = useCallback((userId: string) => {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelectedMemberIds(new Set());
    } else {
      setSelectedMemberIds(new Set(membersExcludingCurrentUser.map((m) => m.userId)));
    }
  }, [allSelected, membersExcludingCurrentUser]);

  const handleNextToInvite = useCallback(() => {
    setStep('invite');
  }, []);

  const handleBackToInfo = useCallback(() => {
    setStep('info');
  }, []);

  const handleCreateMeeting = useCallback(async () => {
    if (!selectedTeamId || !meetingTitle.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const meeting = await meetingService.createMeeting(selectedTeamId, {
        title: meetingTitle.trim(),
        description: meetingDescription.trim() || undefined,
      });

      setCreatedMeetingId(meeting.id);
      localStorage.setItem(LAST_MEETING_TEAM_KEY, selectedTeamId);

      // Filter out current user (safety) and invite selected members
      const membersToInvite = Array.from(selectedMemberIds).filter(
        (userId) => userId !== user?.id,
      );

      const results = await Promise.allSettled(
        membersToInvite.map((userId) =>
          meetingService.addParticipant(meeting.id, {
            userId,
            role: 'participant' as const,
          }),
        ),
      );

      const succeeded = results.filter((r) => r.status === 'fulfilled').length;
      const failed = results.filter((r) => r.status === 'rejected').length;

      setInviteResults({ succeeded, failed });
      setStep('success');
    } catch {
      setError('회의를 만들지 못했어요. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedTeamId, meetingTitle, meetingDescription, selectedMemberIds, user?.id]);

  const handleEnterMeeting = useCallback(async () => {
    if (!createdMeetingId) return;
    try {
      await api.post(`/meetings/${createdMeetingId}/start`);
      navigate(`/dashboard/meetings/${createdMeetingId}/room`);
    } catch {
      setError('회의실에 입장하지 못했어요. 잠시 후 다시 시도해주세요.');
    }
  }, [createdMeetingId, navigate]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    },
    [onClose],
  );

  const getRoleBadge = (role: string) => {
    const colors: Record<string, string> = {
      owner: 'bg-amber-500/20 text-amber-400',
      admin: 'bg-blue-500/20 text-blue-400',
      member: 'bg-white/10 text-white/60',
    };
    return colors[role] || colors.member;
  };

  const getRoleLabel = (role: string) => {
    const labels: Record<string, string> = {
      owner: '소유자',
      admin: '관리자',
      member: '멤버',
    };
    return labels[role] || '멤버';
  };

  // --- Step 3: Success ---
  if (step === 'success') {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="pt-4 pb-1 px-1 space-y-3"
        onKeyDown={handleKeyDown}
      >
        <div className="flex items-center gap-2 text-sm text-green-400" role="status">
          <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center">
            <Check className="w-3 h-3" />
          </div>
          <span>회의가 만들어졌어요</span>
        </div>
        {inviteResults.succeeded > 0 && (
          <p className="text-xs text-white/50">
            {inviteResults.succeeded}명에게 초대를 보냈어요
            {inviteResults.failed > 0 && (
              <span className="text-amber-400 ml-2">{inviteResults.failed}명 초대에 문제가 있었어요</span>
            )}
          </p>
        )}
        {error && <p className="text-xs text-red-400" role="alert">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-white/50 hover:text-white/70 hover:bg-white/5"
          >
            닫기
          </Button>
          <Button size="sm" onClick={handleEnterMeeting} className="gap-1.5">
            회의실로 이동
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      </motion.div>
    );
  }

  // --- Step 2: Invite ---
  if (step === 'invite') {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="pt-4 pb-1 px-1 space-y-3"
        onKeyDown={handleKeyDown}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs text-white/40">
            {selectedCount}/{membersExcludingCurrentUser.length}명 선택
          </span>
          <button
            onClick={toggleSelectAll}
            className="text-xs text-purple-400 hover:text-purple-300 transition-colors"
            disabled={isLoadingMembers || membersExcludingCurrentUser.length === 0}
          >
            {allSelected ? '전체 해제' : '전체 선택'}
          </button>
        </div>

        {isLoadingMembers ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-4 h-4 animate-spin text-white/40" />
          </div>
        ) : membersExcludingCurrentUser.length === 0 ? (
          <p className="text-xs text-white/40 text-center py-3">초대할 수 있는 팀원이 없어요</p>
        ) : (
          <div className="max-h-[200px] overflow-y-auto scrollbar-hide space-y-1">
            {membersExcludingCurrentUser.map((member) => {
              const isSelected = selectedMemberIds.has(member.userId);
              const memberName = member.user?.name || '이름 미확인';

              return (
                <button
                  key={member.id}
                  onClick={() => toggleMember(member.userId)}
                  className={cn(
                    'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all',
                    isSelected
                      ? 'bg-purple-500/10 border border-purple-400/20'
                      : 'hover:bg-white/5 border border-transparent',
                  )}
                >
                  <div
                    className={cn(
                      'w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-all',
                      isSelected
                        ? 'bg-purple-500 border-purple-500'
                        : 'border-white/20',
                    )}
                  >
                    {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                  </div>
                  <span className="text-xs text-white/80 flex-1 truncate">{memberName}</span>
                  <span
                    className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0',
                      getRoleBadge(member.role),
                    )}
                  >
                    {getRoleLabel(member.role)}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {error && <p className="text-xs text-red-400" role="alert">{error}</p>}

        <div className="flex justify-between gap-2">
          <button
            onClick={handleBackToInfo}
            disabled={isSubmitting}
            className="flex items-center gap-1 px-3 py-1.5 text-xs text-white/40 hover:text-white/60 transition-colors rounded-lg hover:bg-white/5"
          >
            <ChevronLeft className="w-3 h-3" />
            이전
          </button>
          <Button
            size="sm"
            onClick={handleCreateMeeting}
            disabled={isSubmitting}
            className="gap-1.5 text-xs"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                만드는 중...
              </>
            ) : selectedCount > 0 ? (
              `회의 만들기 (${selectedCount}명 초대)`
            ) : (
              '회의 만들기'
            )}
          </Button>
        </div>
      </motion.div>
    );
  }

  // --- Step 1: Info ---
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.1 }}
      className="pt-4 pb-1 px-1 space-y-3"
      onKeyDown={handleKeyDown}
    >
      <div className="flex gap-2">
        {teams.length > 1 && (
          <select
            value={selectedTeamId}
            onChange={(e) => setSelectedTeamId(e.target.value)}
            className="w-[140px] bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-purple-400/40 transition-colors"
          >
            <option value="">팀 선택</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id} className="bg-gray-900">
                {team.name}
              </option>
            ))}
          </select>
        )}
        <Input
          value={meetingTitle}
          onChange={(e) => setMeetingTitle(e.target.value)}
          placeholder="회의 제목을 입력해주세요"
          autoFocus
          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 outline-none focus:border-purple-400/40 transition-colors"
        />
      </div>

      <textarea
        value={meetingDescription}
        onChange={(e) => setMeetingDescription(e.target.value)}
        placeholder="회의 내용을 간단히 적어주세요 (선택)"
        rows={2}
        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 outline-none focus:border-purple-400/40 transition-colors resize-none"
      />

      {error && <p className="text-xs text-red-400" role="alert">{error}</p>}

      <div className="flex justify-end gap-2">
        <button
          onClick={onClose}
          className="flex items-center gap-1 px-3 py-1.5 text-xs text-white/40 hover:text-white/60 transition-colors rounded-lg hover:bg-white/5"
        >
          <X className="w-3 h-3" />
          취소
        </button>
        <Button
          size="sm"
          onClick={handleNextToInvite}
          disabled={!canProceedToInvite}
          className="gap-1.5 text-xs"
        >
          다음
          <ChevronRight className="w-3 h-3" />
        </Button>
      </div>
    </motion.div>
  );
}
