import { useState, useEffect } from 'react';
import { Settings, Check, Copy, RefreshCw, Trash2, Plus, Pencil, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/app/components/ui';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { useTeamStore } from '@/stores/teamStore';
import {
  MAX_TEAM_MEMBERS,
  TEAM_ROLE_COLORS,
  TEAM_ROLE_LABELS,
} from '@/constants';
import type { TeamMember, TeamRole, TeamWithMembers } from '@/types';

interface TeamSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  team: TeamWithMembers;
  teamId: string;
  currentUserId: string | undefined;
  isOwner: boolean;
  canManageMembers: boolean;
  onInvite: (email: string, role: TeamRole) => Promise<void>;
  onUpdateRole: (userId: string, role: TeamRole) => Promise<void>;
  onRemove: (userId: string, name: string) => void;
  onDeleteTeam: () => void;
  deleting: boolean;
}

export function TeamSettingsDialog({
  open,
  onOpenChange,
  team,
  teamId,
  currentUserId,
  isOwner,
  canManageMembers,
  onInvite,
  onUpdateRole,
  onRemove,
  onDeleteTeam,
  deleting,
}: TeamSettingsDialogProps) {
  // Invite form state
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<TeamRole>('member');
  const [inviting, setInviting] = useState(false);
  const [inviteFeedback, setInviteFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Member editing state - batch edit mode
  const [editMode, setEditMode] = useState(false);
  const [pendingRoles, setPendingRoles] = useState<Record<string, TeamRole>>({});
  const [pendingRemovals, setPendingRemovals] = useState<Set<string>>(new Set());
  const [savingEdits, setSavingEdits] = useState(false);

  // Invite link state
  const {
    inviteLink,
    inviteLinkLoading,
    generateInviteLink,
    fetchInviteLink,
    deactivateInviteLink,
  } = useTeamStore();
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const memberCount = team.members.length;
  const isTeamFull = memberCount >= MAX_TEAM_MEMBERS;

  useEffect(() => {
    if (open && canManageMembers) {
      fetchInviteLink(teamId);
    }
  }, [open, teamId, canManageMembers, fetchInviteLink]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    if (isTeamFull) {
      setInviteFeedback({ type: 'error', message: `팀 정원이 가득 찼습니다 (최대 ${MAX_TEAM_MEMBERS}명)` });
      setTimeout(() => setInviteFeedback(null), 3000);
      return;
    }

    setInviting(true);
    setInviteFeedback(null);
    try {
      await onInvite(inviteEmail.trim(), inviteRole);
      setInviteFeedback({ type: 'success', message: `${inviteEmail.trim()} 초대 완료` });
      setInviteEmail('');
      setInviteRole('member');
      setTimeout(() => setInviteFeedback(null), 3000);
    } catch {
      setInviteFeedback({ type: 'error', message: '초대에 실패했습니다' });
      setTimeout(() => setInviteFeedback(null), 3000);
    } finally {
      setInviting(false);
    }
  };

  const handleEnterEditMode = () => {
    const initial: Record<string, TeamRole> = {};
    team.members.forEach((m) => {
      if (m.role !== 'owner') {
        initial[m.userId] = m.role as TeamRole;
      }
    });
    setPendingRoles(initial);
    setEditMode(true);
  };

  const handleCancelEdit = () => {
    setEditMode(false);
    setPendingRoles({});
    setPendingRemovals(new Set());
  };

  const handleToggleRemoval = (userId: string) => {
    setPendingRemovals((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const handleSaveEdits = async () => {
    setSavingEdits(true);
    try {
      const roleUpdates = Object.entries(pendingRoles).filter(
        ([userId, role]) => {
          if (pendingRemovals.has(userId)) return false;
          const member = team.members.find((m) => m.userId === userId);
          return member && member.role !== role;
        }
      );

      await Promise.all([
        ...roleUpdates.map(([userId, role]) => onUpdateRole(userId, role)),
        ...Array.from(pendingRemovals).map((userId) => {
          const member = team.members.find((m) => m.userId === userId);
          return onRemove(userId, member?.user?.name || 'this member');
        }),
      ]);

      setEditMode(false);
      setPendingRoles({});
      setPendingRemovals(new Set());
    } finally {
      setSavingEdits(false);
    }
  };

  const handleCopy = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink.inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('클립보드 복사에 실패했습니다.');
    }
  };

  const handleGenerate = async () => {
    setError(null);
    try {
      await generateInviteLink(teamId);
    } catch {
      setError('초대 링크 생성에 실패했습니다.');
    }
  };

  const handleDeactivate = async () => {
    setError(null);
    try {
      await deactivateInviteLink(teamId);
    } catch {
      setError('초대 링크 비활성화에 실패했습니다.');
    }
  };

  const formatExpiresAt = (expiresAt: string) => {
    const expires = new Date(expiresAt);
    const now = new Date();
    const diffMs = expires.getTime() - now.getTime();

    if (diffMs <= 0) return '만료됨';

    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}분 후 만료`;
    const diffHour = Math.floor(diffMin / 60);
    return `${diffHour}시간 ${diffMin % 60}분 후 만료`;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent variant="glass" className="max-w-lg !top-[20%] !translate-y-0">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center">
              <Settings className="w-5 h-5 text-blue-400" />
            </div>
            <div className="flex-1">
              <DialogTitle className="text-white">팀 설정</DialogTitle>
              <DialogDescription className="text-white/50">
                멤버 관리, 초대, 팀 설정
              </DialogDescription>
            </div>
            {canManageMembers && !inviteLink && !isTeamFull && (
              <Button
                variant="outline"
                onClick={handleGenerate}
                isLoading={inviteLinkLoading}
                className="flex-shrink-0"
              >
                Invite Link
              </Button>
            )}
          </div>
          {/* Invite Link - animated slide */}
          <div
            className="grid transition-[grid-template-rows] duration-300 ease-in-out"
            style={{ gridTemplateRows: canManageMembers && inviteLink && !isTeamFull ? '1fr' : '0fr' }}
          >
            <div className="overflow-hidden">
              <div className="mt-2 flex items-stretch rounded-lg border border-white/10 overflow-hidden">
                <div
                  className="group relative cursor-pointer flex-1 min-w-0"
                  onClick={handleCopy}
                  title={copied ? 'Copied!' : inviteLink ? `Click to copy · ${formatExpiresAt(inviteLink.expiresAt)}` : ''}
                >
                  <input
                    type="text"
                    readOnly
                    value={inviteLink?.inviteUrl ?? ''}
                    className={cn(
                      'w-full h-full px-3 py-2 pr-8 bg-transparent text-sm font-mono truncate cursor-pointer transition-all border-none outline-none',
                      copied ? 'text-green-400' : 'text-white'
                    )}
                  />
                  <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
                    {copied ? (
                      <Check className="w-4 h-4 text-green-400" />
                    ) : (
                      <Copy className="w-4 h-4 text-white/30 group-hover:text-white/60 transition-colors" />
                    )}
                  </div>
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={inviteLinkLoading}
                  className="px-4 border-l border-white/10 text-white/50 hover:bg-white/10 hover:text-white transition-colors disabled:opacity-50 flex-shrink-0"
                  title="갱신"
                >
                  <RefreshCw className={cn('w-5 h-5', inviteLinkLoading && 'animate-spin')} />
                </button>
                <button
                  onClick={handleDeactivate}
                  disabled={inviteLinkLoading}
                  className="px-4 border-l border-white/10 text-red-400/50 hover:bg-red-500/10 hover:text-red-400 transition-colors disabled:opacity-50 flex-shrink-0"
                  title="삭제"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
          {error && (
            <div className="mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
              {error}
            </div>
          )}
        </DialogHeader>

        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">
            Team Members ({memberCount}/{MAX_TEAM_MEMBERS})
          </h3>
          {canManageMembers && (
            editMode ? (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={handleCancelEdit}
                  disabled={savingEdits}
                  className="p-2 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                  title="취소"
                >
                  <X className="w-5 h-5" />
                </button>
                <button
                  onClick={handleSaveEdits}
                  disabled={savingEdits}
                  className="p-2 rounded-lg text-green-400 hover:bg-green-500/10 transition-colors disabled:opacity-50"
                  title="저장"
                >
                  <Check className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <button
                onClick={handleEnterEditMode}
                className="p-2 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/5 transition-colors"
                title="멤버 편집"
              >
                <Pencil className="w-5 h-5" />
              </button>
            )
          )}
        </div>

        <div className="max-h-[60vh] overflow-y-auto scrollbar-hide space-y-6 pr-1">
          {/* Section 1: Members */}
          <div>

            {/* Invite Form - hidden in edit mode */}
            <div
              className="grid transition-[grid-template-rows] duration-300 ease-in-out"
              style={{ gridTemplateRows: showInviteForm && !editMode ? '1fr' : '0fr' }}
            >
              <div className="overflow-hidden">
                <form onSubmit={handleInvite} className="mb-3 space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="이메일 주소"
                      required
                      className="flex-1 min-w-0 px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-white/30 focus:outline-none focus:border-mit-primary/50"
                    />
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as TeamRole)}
                      className="appearance-none px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white/70 focus:outline-none focus:border-mit-primary/50 cursor-pointer"
                    >
                      <option value="member" className="bg-gray-800">Member</option>
                      <option value="admin" className="bg-gray-800">Admin</option>
                    </select>
                    <Button type="submit" isLoading={inviting}>
                      초대
                    </Button>
                  </div>
                  {inviteFeedback && (
                    <div className={cn(
                      'text-xs px-3 py-1.5 rounded-lg transition-all',
                      inviteFeedback.type === 'success'
                        ? 'bg-green-500/10 text-green-400'
                        : 'bg-red-500/10 text-red-400'
                    )}>
                      {inviteFeedback.type === 'success' ? '✓' : '✗'} {inviteFeedback.message}
                    </div>
                  )}
                </form>
              </div>
            </div>

            {/* Member List */}
            <div className="rounded-lg border border-white/10 divide-y divide-white/10">
              {team.members.map((member) => (
                <MemberRow
                  key={member.id}
                  member={member}
                  currentUserId={currentUserId}
                  isOwner={isOwner}
                  canManageMembers={canManageMembers}
                  editMode={editMode}
                  pendingRole={pendingRoles[member.userId]}
                  pendingRemoval={pendingRemovals.has(member.userId)}
                  onRoleChange={(role) => setPendingRoles((prev) => ({ ...prev, [member.userId]: role }))}
                  onToggleRemoval={() => handleToggleRemoval(member.userId)}
                />
              ))}

              {/* Add Member Button - hidden in edit mode */}
              {canManageMembers && !isTeamFull && !editMode && (
                <button
                  onClick={() => setShowInviteForm(!showInviteForm)}
                  className="w-full px-3 py-2.5 flex items-center justify-center gap-2 text-sm text-white/40 hover:text-white/70 hover:bg-white/5 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  {showInviteForm ? '취소' : '멤버 초대'}
                </button>
              )}
            </div>
          </div>

          {/* Section 2: Danger Zone */}
          {isOwner && (
            <div className="border-t border-white/10 pt-6">
              <div className="p-4 rounded-lg border-2 border-red-500/30 bg-red-500/5 flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-red-400">Danger Zone</h3>
                  <p className="text-xs text-white/50 mt-1">
                    팀을 삭제하면 되돌릴 수 없습니다.
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={onDeleteTeam}
                  isLoading={deleting}
                  className="text-red-400 border-red-500/30 hover:bg-red-500/20 flex-shrink-0"
                >
                  Delete Team
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface MemberRowProps {
  member: TeamMember;
  currentUserId: string | undefined;
  isOwner: boolean;
  canManageMembers: boolean;
  editMode: boolean;
  pendingRole: TeamRole | undefined;
  pendingRemoval: boolean;
  onRoleChange: (role: TeamRole) => void;
  onToggleRemoval: () => void;
}

function MemberRow({
  member,
  currentUserId,
  isOwner,
  canManageMembers,
  editMode,
  pendingRole,
  pendingRemoval,
  onRoleChange,
  onToggleRemoval,
}: MemberRowProps) {
  const isCurrentUser = member.userId === currentUserId;
  const isMemberOwner = member.role === 'owner';

  const canRemove =
    (isOwner && !isCurrentUser) ||
    (canManageMembers && member.role === 'member' && !isCurrentUser) ||
    (isCurrentUser && !isMemberOwner);

  const canEditRole = isOwner && !isMemberOwner;
  const displayRole = pendingRole ?? (member.role as TeamRole);
  const roleChanged = pendingRole !== undefined && pendingRole !== member.role;

  return (
    <div className={cn(
      'px-3 py-2.5 flex items-center justify-between transition-all',
      pendingRemoval && 'opacity-40 line-through'
    )}>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">
          {member.user?.name || 'Unknown User'}
          {isCurrentUser && (
            <span className="text-white/50 text-xs ml-2">(You)</span>
          )}
        </p>
        <p className="text-xs text-white/60 truncate">{member.user?.email}</p>
      </div>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {editMode && canEditRole && !pendingRemoval ? (
          <select
            value={displayRole}
            onChange={(e) => onRoleChange(e.target.value as TeamRole)}
            className={cn(
              'appearance-none px-2 py-0.5 rounded-full text-xs font-medium border cursor-pointer transition-all',
              roleChanged
                ? 'bg-amber-500/15 border-amber-500/30 text-amber-400'
                : 'bg-white/5 border-white/10 text-white/70'
            )}
          >
            <option value="member" className="bg-gray-800">Member</option>
            <option value="admin" className="bg-gray-800">Admin</option>
          </select>
        ) : (
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              TEAM_ROLE_COLORS[member.role as TeamRole]
            }`}
          >
            {TEAM_ROLE_LABELS[member.role as TeamRole]}
          </span>
        )}
        {editMode && canRemove && (
          <button
            onClick={onToggleRemoval}
            className={cn(
              'p-1.5 rounded-lg transition-colors',
              pendingRemoval
                ? 'text-white/50 hover:text-white hover:bg-white/10'
                : 'text-red-400/50 hover:text-red-400 hover:bg-red-500/10'
            )}
            title={pendingRemoval ? '되돌리기' : '내보내기'}
          >
            {pendingRemoval ? <RefreshCw className="w-4 h-4" /> : <X className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  );
}
