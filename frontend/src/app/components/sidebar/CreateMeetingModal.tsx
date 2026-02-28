import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Users, ChevronRight, ChevronLeft, ArrowRight } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  Button,
  Input,
  Avatar,
  AvatarFallback,
} from '@/app/components/ui';
import { useTeamStore } from '@/stores/teamStore';
import { teamService } from '@/services/teamService';
import { meetingService } from '@/services/meetingService';
import api from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { cn } from '@/lib/utils';
import type { TeamMember } from '@/types';

interface CreateMeetingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const inputBaseClasses = 'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-white/30 outline-none focus:border-mit-primary/50 focus:ring-2 focus:ring-mit-primary/20 transition-all';

export function CreateMeetingModal({ open, onOpenChange }: CreateMeetingModalProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { teams } = useTeamStore();
  const {
    step,
    createdMeetingId,
    createdMeetingTitle,
    setStep,
    setCreatedMeeting,
    closeModal,
  } = useMeetingModalStore();

  // Step 1: Meeting Info
  const [selectedTeamId, setSelectedTeamId] = useState<string>('');
  const [meetingTitle, setMeetingTitle] = useState('');
  const [meetingDescription, setMeetingDescription] = useState('');

  // Step 2: Invite Members
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [isLoadingMembers, setIsLoadingMembers] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [submitError, setSubmitError] = useState<string | null>(null);

  // Step 3: Success
  const [inviteResults, setInviteResults] = useState<{
    succeeded: number;
    failed: number;
  }>({ succeeded: 0, failed: 0 });

  // Load members when entering step 2
  useEffect(() => {
    if (step === 'invite' && selectedTeamId && open) {
      setIsLoadingMembers(true);
      setMembersError(null);
      teamService
        .getTeam(selectedTeamId)
        .then((team) => {
          setMembers(team.members || []);
        })
        .catch((error) => {
          setMembersError('팀원 정보를 불러오지 못했어요. 잠시 후 다시 시도해주세요.');
          console.error('Failed to load team members:', error);
        })
        .finally(() => {
          setIsLoadingMembers(false);
        });
    }
  }, [step, selectedTeamId, open]);

  // Reset state when modal closes
  useEffect(() => {
    if (!open) {
      setSelectedTeamId('');
      setMeetingTitle('');
      setMeetingDescription('');
      setMembers([]);
      setSelectedMemberIds(new Set());
      setInviteResults({ succeeded: 0, failed: 0 });
      setMembersError(null);
      setSubmitError(null);
    }
  }, [open]);

  const handleClose = useCallback(() => {
    closeModal();
    onOpenChange(false);
  }, [closeModal, onOpenChange]);

  const handleNextToInvite = useCallback(() => {
    setStep('invite');
  }, [setStep]);

  const handleBackToInfo = useCallback(() => {
    setStep('info');
  }, [setStep]);

  const handleCreateMeeting = useCallback(async () => {
    if (!selectedTeamId || !meetingTitle) return;

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const meeting = await meetingService.createMeeting(selectedTeamId, {
        title: meetingTitle,
        description: meetingDescription,
      });

      setCreatedMeeting(meeting.id, meetingTitle);

      // Filter out current user and invite selected members
      const membersToInvite = Array.from(selectedMemberIds).filter(
        (userId) => userId !== user?.id
      );

      const results = await Promise.allSettled(
        membersToInvite.map((userId) =>
          meetingService.addParticipant(meeting.id, {
            userId,
            role: 'participant' as const,
          })
        )
      );

      const succeeded = results.filter((r) => r.status === 'fulfilled').length;
      const failed = results.filter((r) => r.status === 'rejected').length;

      setInviteResults({ succeeded, failed });
      setStep('success');
    } catch (error) {
      console.error('Failed to create meeting:', error);
      setSubmitError('회의를 만들지 못했어요. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsSubmitting(false);
    }
  }, [
    selectedTeamId,
    meetingTitle,
    meetingDescription,
    selectedMemberIds,
    user?.id,
    setCreatedMeeting,
    setStep,
  ]);

  const handleEnterMeeting = useCallback(async () => {
    if (createdMeetingId) {
      try {
        await api.post(`/meetings/${createdMeetingId}/start`);
        navigate(`/dashboard/meetings/${createdMeetingId}/room`);
        handleClose();
      } catch (error) {
        console.error('Failed to start meeting:', error);
      }
    }
  }, [createdMeetingId, navigate, handleClose]);

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

  const membersExcludingCurrentUser = members.filter(
    (m) => m.userId !== user?.id
  );

  const allSelected =
    membersExcludingCurrentUser.length > 0 &&
    membersExcludingCurrentUser.every((m) => selectedMemberIds.has(m.userId));

  const toggleSelectAll = useCallback(() => {
    if (allSelected) {
      setSelectedMemberIds(new Set());
    } else {
      setSelectedMemberIds(
        new Set(membersExcludingCurrentUser.map((m) => m.userId))
      );
    }
  }, [allSelected, membersExcludingCurrentUser]);

  const selectedCount = selectedMemberIds.size;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent variant="glass" className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-mit-primary/20 to-mit-secondary/20 flex items-center justify-center">
              <Users className="w-6 h-6 text-mit-primary" />
            </div>
            <div>
              <DialogTitle>새 회의 만들기</DialogTitle>
              <DialogDescription>
                {step === 'info' && '회의 정보를 입력해주세요'}
                {step === 'invite' && '팀원을 초대해주세요'}
                {step === 'success' && '회의가 만들어졌어요'}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Step Indicator */}
        <StepIndicator currentStep={step} />

        {/* Step 1: Meeting Info */}
        {step === 'info' && (
          <MeetingInfoStep
            teams={teams}
            selectedTeamId={selectedTeamId}
            onTeamIdChange={setSelectedTeamId}
            meetingTitle={meetingTitle}
            onTitleChange={setMeetingTitle}
            meetingDescription={meetingDescription}
            onDescriptionChange={setMeetingDescription}
            onCancel={handleClose}
            onNext={handleNextToInvite}
          />
        )}

        {/* Step 2: Invite Members */}
        {step === 'invite' && (
          <InviteMembersStep
            members={members}
            isLoadingMembers={isLoadingMembers}
            membersError={membersError}
            submitError={submitError}
            currentUserId={user?.id || ''}
            selectedMemberIds={selectedMemberIds}
            onToggleMember={toggleMember}
            onToggleSelectAll={toggleSelectAll}
            allSelected={allSelected}
            selectedCount={selectedCount}
            totalCount={membersExcludingCurrentUser.length}
            onBack={handleBackToInfo}
            onCreateMeeting={handleCreateMeeting}
            isSubmitting={isSubmitting}
          />
        )}

        {/* Step 3: Success */}
        {step === 'success' && (
          <SuccessStep
            meetingTitle={createdMeetingTitle}
            inviteResults={inviteResults}
            onClose={handleClose}
            onEnterMeeting={handleEnterMeeting}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

interface StepIndicatorProps {
  currentStep: 'info' | 'invite' | 'success';
}

function StepIndicator({ currentStep }: StepIndicatorProps) {
  const steps = [
    { key: 'info', label: '정보' },
    { key: 'invite', label: '초대' },
    { key: 'success', label: '완료' },
  ] as const;

  const currentIndex = steps.findIndex((s) => s.key === currentStep);

  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {steps.map((step, index) => {
        const isCompleted = index < currentIndex;
        const isCurrent = index === currentIndex;
        const isPending = index > currentIndex;

        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all',
                  isCompleted &&
                    'bg-green-500/20 text-green-400',
                  isCurrent && 'bg-mit-primary text-white',
                  isPending && 'bg-white/10 text-white/30'
                )}
              >
                {isCompleted ? (
                  <Check className="w-4 h-4" />
                ) : (
                  index + 1
                )}
              </div>
              <span
                className={cn(
                  'text-xs mt-1 transition-all',
                  isCurrent ? 'text-white' : 'text-white/40'
                )}
              >
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={cn(
                  'w-12 h-0.5 mx-2 mb-5 transition-all',
                  isCompleted
                    ? 'bg-green-500/30'
                    : 'bg-white/10'
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

interface MeetingInfoStepProps {
  teams: Array<{ id: string; name: string }>;
  selectedTeamId: string;
  onTeamIdChange: (teamId: string) => void;
  meetingTitle: string;
  onTitleChange: (title: string) => void;
  meetingDescription: string;
  onDescriptionChange: (description: string) => void;
  onCancel: () => void;
  onNext: () => void;
}

function MeetingInfoStep({
  teams,
  selectedTeamId,
  onTeamIdChange,
  meetingTitle,
  onTitleChange,
  meetingDescription,
  onDescriptionChange,
  onCancel,
  onNext,
}: MeetingInfoStepProps) {
  const canProceed = Boolean(selectedTeamId && meetingTitle.trim());

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm text-white/70">팀 선택</label>
        <select
          value={selectedTeamId}
          onChange={(e) => onTeamIdChange(e.target.value)}
          className={inputBaseClasses}
        >
          <option value="">팀을 선택해주세요</option>
          {teams.map((team) => (
            <option key={team.id} value={team.id} className="bg-gray-900">
              {team.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label className="text-sm text-white/70">회의 제목</label>
        <Input
          value={meetingTitle}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="회의 제목을 입력해주세요"
          className={inputBaseClasses}
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm text-white/70">회의 설명 (선택)</label>
        <textarea
          value={meetingDescription}
          onChange={(e) => onDescriptionChange(e.target.value)}
          placeholder="회의 내용을 간단히 적어주세요"
          className={cn(inputBaseClasses, 'min-h-[100px] resize-none')}
        />
      </div>

      <div className="flex gap-2 pt-4">
        <Button
          variant="ghost"
          onClick={onCancel}
          className={cn(
            'flex-1 hover:bg-white/20 hover:text-white',
            canProceed
              ? 'bg-white/10 text-white/70'
              : 'bg-white/5 text-white/40'
          )}
        >
          취소
        </Button>
        <Button
          onClick={onNext}
          disabled={!canProceed}
          className="flex-1 gap-2"
        >
          다음
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

interface InviteMembersStepProps {
  members: TeamMember[];
  isLoadingMembers: boolean;
  membersError: string | null;
  submitError: string | null;
  currentUserId: string;
  selectedMemberIds: Set<string>;
  onToggleMember: (userId: string) => void;
  onToggleSelectAll: () => void;
  allSelected: boolean;
  selectedCount: number;
  totalCount: number;
  onBack: () => void;
  onCreateMeeting: () => void;
  isSubmitting: boolean;
}

function InviteMembersStep({
  members,
  isLoadingMembers,
  membersError,
  submitError,
  currentUserId,
  selectedMemberIds,
  onToggleMember,
  onToggleSelectAll,
  allSelected,
  selectedCount,
  totalCount,
  onBack,
  onCreateMeeting,
  isSubmitting,
}: InviteMembersStepProps) {
  const getRoleBadge = (role: string) => {
    const colors = {
      owner: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      admin: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      member: 'bg-white/10 text-white/70 border-white/20',
    };
    return colors[role as keyof typeof colors] || colors.member;
  };

  return (
    <div className="space-y-4">
      {/* Select All Toggle */}
      <div className="flex items-center justify-between">
        <button
          onClick={onToggleSelectAll}
          className="text-sm text-mit-primary hover:text-mit-primary/80 transition-colors"
          disabled={isLoadingMembers || totalCount === 0}
        >
          {allSelected ? '전체 해제' : '전체 선택'}
        </button>
        <span className="text-sm text-white/50">
          {selectedCount}/{totalCount}명 선택
        </span>
      </div>

      {/* Members List */}
      {isLoadingMembers ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-12 bg-white/5 animate-pulse rounded-lg"
            />
          ))}
        </div>
      ) : membersError ? (
        <div className="text-center py-8 text-red-400 text-sm">
          {membersError}
        </div>
      ) : members.length === 0 ? (
        <div className="text-center py-8 text-white/50 text-sm">
          아직 초대할 수 있는 팀원이 없어요. 팀 설정에서 멤버를 초대해보세요.
        </div>
      ) : (
        <div className="max-h-[300px] overflow-y-auto scrollbar-hide">
          <div className="space-y-2">
            {members.map((member) => {
              const isCurrentUser = member.userId === currentUserId;
              const isSelected = selectedMemberIds.has(member.userId);
              const memberName = member.user?.name || '알 수 없음';

              return (
                <div
                  key={member.id}
                  className={cn(
                    'flex items-center gap-3 p-3 rounded-lg border transition-all',
                    isCurrentUser
                      ? 'bg-mit-primary/10 border-mit-primary/30'
                      : 'bg-white/5 border-white/10 hover:border-white/20'
                  )}
                >
                  {/* Checkbox */}
                  <div
                    role="checkbox"
                    aria-checked={isSelected}
                    tabIndex={isCurrentUser ? -1 : 0}
                    onClick={() => !isCurrentUser && onToggleMember(member.userId)}
                    onKeyDown={(e) => {
                      if (!isCurrentUser && (e.key === ' ' || e.key === 'Enter')) {
                        e.preventDefault();
                        onToggleMember(member.userId);
                      }
                    }}
                    className={cn(
                      'w-5 h-5 rounded border-2 flex items-center justify-center transition-all',
                      isCurrentUser
                        ? 'border-white/10 bg-white/5 cursor-not-allowed'
                        : isSelected
                        ? 'bg-mit-primary border-mit-primary cursor-pointer'
                        : 'border-white/20 hover:border-white/40 cursor-pointer'
                    )}
                  >
                    {isSelected && !isCurrentUser && (
                      <Check className="w-3 h-3 text-white" />
                    )}
                  </div>

                  {/* Avatar */}
                  <Avatar className="w-8 h-8">
                    <AvatarFallback className="bg-gradient-to-br from-mit-primary/30 to-mit-secondary/30 text-white text-xs">
                      {memberName.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>

                  {/* Name and Role */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">
                      {memberName}
                    </p>
                  </div>

                  {/* Role Badge or Host Label */}
                  {isCurrentUser ? (
                    <span className="text-xs px-2 py-1 rounded-full bg-mit-primary/20 text-mit-primary border border-mit-primary/30">
                      호스트 (자동)
                    </span>
                  ) : (
                    <span
                      className={cn(
                        'text-xs px-2 py-1 rounded-full border',
                        getRoleBadge(member.role)
                      )}
                    >
                      {member.role === 'owner'
                        ? '소유자'
                        : member.role === 'admin'
                        ? '관리자'
                        : '멤버'}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error Message */}
      {submitError && (
        <div className="text-sm text-red-400 bg-red-400/10 px-3 py-2 rounded-lg">
          {submitError}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2 pt-4">
        <Button
          variant="ghost"
          onClick={onBack}
          className="gap-2 bg-white/10 text-white/70 hover:bg-white/20 hover:text-white"
          disabled={isSubmitting}
        >
          <ChevronLeft className="w-4 h-4" />
          이전
        </Button>
        <Button
          onClick={onCreateMeeting}
          disabled={isSubmitting}
          className="flex-1"
        >
          {isSubmitting
            ? '만드는 중...'
            : `회의 만들기 (${selectedCount}명 초대)`}
        </Button>
      </div>
    </div>
  );
}

interface SuccessStepProps {
  meetingTitle: string | null;
  inviteResults: { succeeded: number; failed: number };
  onClose: () => void;
  onEnterMeeting: () => void;
}

function SuccessStep({
  meetingTitle,
  inviteResults,
  onClose,
  onEnterMeeting,
}: SuccessStepProps) {
  return (
    <div className="space-y-6 text-center">
      {/* Success Icon */}
      <div className="flex justify-center">
        <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center">
          <Check className="w-8 h-8 text-green-400" />
        </div>
      </div>

      {/* Title */}
      <div>
        <h3 className="text-xl font-semibold text-white mb-2">
          회의가 만들어졌어요!
        </h3>
        <p className="text-white/70">{meetingTitle}</p>
      </div>

      {/* Invite Results */}
      <div className="space-y-2">
        <p className="text-sm text-green-400">
          {inviteResults.succeeded}명 초대 완료
        </p>
        {inviteResults.failed > 0 && (
          <p className="text-sm text-amber-400">
            ⚠ {inviteResults.failed}명 초대 실패
          </p>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 pt-4">
        <Button variant="ghost" onClick={onClose} className="flex-1 bg-white/10 text-white/70 hover:bg-white/20 hover:text-white">
          닫기
        </Button>
        <Button onClick={onEnterMeeting} className="flex-1 gap-2">
          회의실로 이동
          <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
