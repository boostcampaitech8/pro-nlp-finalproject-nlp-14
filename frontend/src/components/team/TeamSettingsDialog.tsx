import { useState, useEffect } from 'react';
import { Settings, Check, Copy, RefreshCw, Trash2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/app/components/ui';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
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

  // Member editing state
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<TeamRole>('member');

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
      alert(`팀 정원이 가득 찼습니다. (최대 ${MAX_TEAM_MEMBERS}명)`);
      return;
    }

    setInviting(true);
    try {
      await onInvite(inviteEmail.trim(), inviteRole);
      setInviteEmail('');
      setInviteRole('member');
      setShowInviteForm(false);
    } finally {
      setInviting(false);
    }
  };

  const handleUpdateRole = async (userId: string) => {
    await onUpdateRole(userId, editRole);
    setEditingMemberId(null);
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
    if (!confirm('초대 링크를 비활성화하시겠습니까?')) return;
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
            <div>
              <DialogTitle className="text-white">팀 설정</DialogTitle>
              <DialogDescription className="text-white/50">
                멤버 관리, 초대, 팀 설정
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">
            Team Members ({memberCount}/{MAX_TEAM_MEMBERS})
          </h3>
          {canManageMembers && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowInviteForm(!showInviteForm)}
              disabled={isTeamFull && !showInviteForm}
              title={
                isTeamFull
                  ? `팀 정원이 가득 찼습니다 (최대 ${MAX_TEAM_MEMBERS}명)`
                  : undefined
              }
            >
              {showInviteForm ? 'Cancel' : 'Invite Member'}
            </Button>
          )}
        </div>

        <div className="max-h-[60vh] overflow-y-auto space-y-6 pr-1">
          {/* Section 1: Members */}
          <div>

            {/* Invite Form */}
            <div
              className="grid transition-[grid-template-rows] duration-300 ease-in-out"
              style={{ gridTemplateRows: showInviteForm ? '1fr' : '0fr' }}
            >
              <div className="overflow-hidden">
                <div className="p-4 rounded-lg bg-white/5 border border-white/10 mb-4">
                  <h4 className="text-sm font-semibold text-white mb-3">Invite New Member</h4>
                  <form onSubmit={handleInvite} className="space-y-3">
                    <Input
                      label="Email"
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="Enter member's email"
                      required
                    />
                    <div>
                      <label className="block text-sm font-medium text-white/70 mb-1">
                        Role
                      </label>
                      <select
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value as TeamRole)}
                        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-mit-primary/50"
                      >
                        <option value="member" className="bg-gray-800">Member</option>
                        <option value="admin" className="bg-gray-800">Admin</option>
                      </select>
                    </div>
                    <div className="flex justify-end gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setShowInviteForm(false)}
                      >
                        Cancel
                      </Button>
                      <Button type="submit" isLoading={inviting}>
                        Invite
                      </Button>
                    </div>
                  </form>
                </div>
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
                  isEditing={editingMemberId === member.userId}
                  editRole={editRole}
                  onStartEdit={() => {
                    setEditingMemberId(member.userId);
                    setEditRole(member.role as TeamRole);
                  }}
                  onCancelEdit={() => setEditingMemberId(null)}
                  onEditRoleChange={setEditRole}
                  onSaveRole={() => handleUpdateRole(member.userId)}
                  onRemove={() => onRemove(member.userId, member.user?.name || 'this member')}
                />
              ))}
            </div>
          </div>

          {/* Section 2: Invite Link */}
          {canManageMembers && (
            <div className="border-t border-white/10 pt-6">
              <h3 className="text-lg font-semibold text-white mb-3">Invite Link</h3>

              {error && (
                <div className="mb-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}

              {inviteLink ? (
                <div className="p-4 rounded-lg bg-white/5 border border-white/10">
                  <div className="flex items-center gap-2">
                    <div
                      className="group relative cursor-pointer flex-1 min-w-0"
                      onClick={handleCopy}
                      title={copied ? 'Copied!' : `Click to copy · ${formatExpiresAt(inviteLink.expiresAt)}`}
                    >
                      <input
                        type="text"
                        readOnly
                        value={inviteLink.inviteUrl}
                        className={cn(
                          'w-full px-3 py-2 pr-9 bg-white/5 border rounded-lg text-sm font-mono truncate cursor-pointer transition-all',
                          copied
                            ? 'border-green-500/30 text-green-400'
                            : 'border-white/10 text-white hover:border-white/20'
                        )}
                      />
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        {copied ? (
                          <Check className="w-4 h-4 text-green-400" />
                        ) : (
                          <Copy className="w-4 h-4 text-white/30 group-hover:text-white/60 transition-colors" />
                        )}
                      </div>
                    </div>
                    <div className="inline-flex rounded-lg border border-white/10 overflow-hidden flex-shrink-0">
                      <button
                        onClick={handleGenerate}
                        disabled={inviteLinkLoading}
                        className="p-2 text-white/50 hover:bg-white/10 hover:text-white transition-colors disabled:opacity-50"
                        title="Regenerate"
                      >
                        <RefreshCw className={cn('w-3.5 h-3.5', inviteLinkLoading && 'animate-spin')} />
                      </button>
                      <div className="w-px bg-white/10" />
                      <button
                        onClick={handleDeactivate}
                        disabled={inviteLinkLoading}
                        className="p-2 text-red-400/50 hover:bg-red-500/10 hover:text-red-400 transition-colors disabled:opacity-50"
                        title="Deactivate"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <Button
                  variant="outline"
                  onClick={handleGenerate}
                  isLoading={inviteLinkLoading}
                >
                  Generate Invite Link
                </Button>
              )}
            </div>
          )}

          {/* Section 3: Danger Zone */}
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
                  size="sm"
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
  isEditing: boolean;
  editRole: TeamRole;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onEditRoleChange: (role: TeamRole) => void;
  onSaveRole: () => void;
  onRemove: () => void;
}

function MemberRow({
  member,
  currentUserId,
  isOwner,
  canManageMembers,
  isEditing,
  editRole,
  onStartEdit,
  onCancelEdit,
  onEditRoleChange,
  onSaveRole,
  onRemove,
}: MemberRowProps) {
  const isCurrentUser = member.userId === currentUserId;
  const isMemberOwner = member.role === 'owner';

  return (
    <div className="p-4 flex items-center justify-between">
      <div>
        <p className="font-medium text-white">
          {member.user?.name || 'Unknown User'}
          {isCurrentUser && (
            <span className="text-white/50 text-sm ml-2">(You)</span>
          )}
        </p>
        <p className="text-sm text-white/60">{member.user?.email}</p>
      </div>
      <div className="flex items-center gap-2">
        {isEditing ? (
          <>
            <select
              value={editRole}
              onChange={(e) => onEditRoleChange(e.target.value as TeamRole)}
              className="px-2 py-1 bg-white/5 border border-white/10 rounded text-sm text-white"
            >
              <option value="member" className="bg-gray-800">Member</option>
              <option value="admin" className="bg-gray-800">Admin</option>
            </select>
            <Button
              variant="outline"
              onClick={onSaveRole}
              className="text-sm px-2 py-1"
            >
              Save
            </Button>
            <Button
              variant="outline"
              onClick={onCancelEdit}
              className="text-sm px-2 py-1"
            >
              Cancel
            </Button>
          </>
        ) : (
          <>
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                TEAM_ROLE_COLORS[member.role as TeamRole]
              }`}
            >
              {TEAM_ROLE_LABELS[member.role as TeamRole]}
            </span>
            {isOwner && !isMemberOwner && (
              <Button
                variant="outline"
                onClick={onStartEdit}
                className="text-sm px-2 py-1"
              >
                Edit
              </Button>
            )}
            {((canManageMembers && member.role === 'member') ||
              (isCurrentUser && !isMemberOwner)) && (
              <Button
                variant="outline"
                onClick={onRemove}
                className="text-sm px-2 py-1 text-red-400 border-red-500/30 hover:bg-red-500/20"
              >
                Remove
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
