/**
 * 팀 멤버 섹션 컴포넌트
 * 팀 멤버 목록 표시 및 관리 (초대/역할변경/삭제)
 */

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  MAX_TEAM_MEMBERS,
  TEAM_ROLE_COLORS,
  TEAM_ROLE_LABELS,
} from '@/constants';
import type { TeamMember, TeamRole } from '@/types';

interface TeamMemberSectionProps {
  members: TeamMember[];
  currentUserId: string | undefined;
  isOwner: boolean;
  canManageMembers: boolean;
  onInvite: (email: string, role: TeamRole) => Promise<void>;
  onUpdateRole: (userId: string, role: TeamRole) => Promise<void>;
  onRemove: (userId: string, name: string) => void;
}

export function TeamMemberSection({
  members,
  currentUserId,
  isOwner,
  canManageMembers,
  onInvite,
  onUpdateRole,
  onRemove,
}: TeamMemberSectionProps) {
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<TeamRole>('member');
  const [inviting, setInviting] = useState(false);
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<TeamRole>('member');

  // 팀 멤버 수 계산
  const memberCount = members.length;
  const isTeamFull = memberCount >= MAX_TEAM_MEMBERS;

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    // 사전 체크: 팀 정원 초과 시 alert
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

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-900">
          Team Members ({memberCount}/{MAX_TEAM_MEMBERS})
        </h3>
        {canManageMembers && (
          <Button
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

      {/* 멤버 초대 폼 */}
      {showInviteForm && (
        <div className="bg-white rounded-xl shadow-md p-6 mb-4">
          <h4 className="text-lg font-semibold mb-4">Invite New Member</h4>
          <form onSubmit={handleInvite} className="space-y-4">
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
        {members.map((member) => (
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
        <p className="font-medium text-gray-900">
          {member.user?.name || 'Unknown User'}
          {isCurrentUser && (
            <span className="text-gray-500 text-sm ml-2">(You)</span>
          )}
        </p>
        <p className="text-sm text-gray-500">{member.user?.email}</p>
      </div>
      <div className="flex items-center gap-2">
        {isEditing ? (
          // 역할 수정 모드
          <>
            <select
              value={editRole}
              onChange={(e) => onEditRoleChange(e.target.value as TeamRole)}
              className="px-2 py-1 border border-gray-300 rounded text-sm"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
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
          // 일반 표시 모드
          <>
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                TEAM_ROLE_COLORS[member.role as TeamRole]
              }`}
            >
              {TEAM_ROLE_LABELS[member.role as TeamRole]}
            </span>
            {/* owner만 역할 변경 가능, owner 역할은 변경 불가 */}
            {isOwner && !isMemberOwner && (
              <Button
                variant="outline"
                onClick={onStartEdit}
                className="text-sm px-2 py-1"
              >
                Edit
              </Button>
            )}
            {/* owner/admin은 다른 member 삭제 가능, 본인 삭제 가능 (owner 제외) */}
            {((canManageMembers && member.role === 'member') ||
              (isCurrentUser && !isMemberOwner)) && (
              <Button
                variant="outline"
                onClick={onRemove}
                className="text-sm px-2 py-1 text-red-600 border-red-300 hover:bg-red-50"
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
