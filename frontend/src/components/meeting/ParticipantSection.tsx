/**
 * 참여자 섹션 컴포넌트
 * 회의 참여자 목록 표시 및 관리 (추가/수정/삭제) 담당
 */

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import {
  PARTICIPANT_ROLE_COLORS,
  PARTICIPANT_ROLE_LABELS,
} from '@/constants';
import type { MeetingParticipant, ParticipantRole, TeamMember } from '@/types';

interface ParticipantSectionProps {
  participants: MeetingParticipant[];
  availableMembers: TeamMember[];
  currentUserId: string | undefined;
  isHost: boolean;
  onAddParticipant: (userId: string, role: ParticipantRole) => Promise<void>;
  onUpdateRole: (userId: string, role: ParticipantRole) => Promise<void>;
  onRemoveParticipant: (userId: string, name: string) => void;
}

export function ParticipantSection({
  participants,
  availableMembers,
  currentUserId,
  isHost,
  onAddParticipant,
  onUpdateRole,
  onRemoveParticipant,
}: ParticipantSectionProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
  const [participantRole, setParticipantRole] = useState<ParticipantRole>('participant');
  const [adding, setAdding] = useState(false);
  const [editingParticipantId, setEditingParticipantId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<ParticipantRole>('participant');

  // 체크박스 토글 핸들러
  const handleToggleUser = (userId: string) => {
    setSelectedUserIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(userId)) {
        newSet.delete(userId);
      } else {
        newSet.add(userId);
      }
      return newSet;
    });
  };

  // 전체 선택/해제 핸들러
  const handleToggleAll = () => {
    if (selectedUserIds.size === availableMembers.length) {
      // 전체 해제
      setSelectedUserIds(new Set());
    } else {
      // 전체 선택
      setSelectedUserIds(new Set(availableMembers.map((m) => m.userId)));
    }
  };

  const handleAddParticipants = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedUserIds.size === 0) return;

    setAdding(true);
    try {
      // 여러 명을 병렬로 추가
      await Promise.all(
        Array.from(selectedUserIds).map((userId) =>
          onAddParticipant(userId, participantRole)
        )
      );
      setSelectedUserIds(new Set());
      setParticipantRole('participant');
      setShowAddForm(false);
    } finally {
      setAdding(false);
    }
  };

  const handleUpdateRole = async (userId: string) => {
    await onUpdateRole(userId, editRole);
    setEditingParticipantId(null);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-white">
          Participants ({participants.length})
        </h3>
        {isHost && availableMembers.length > 0 && (
          <Button onClick={() => setShowAddForm(!showAddForm)}>
            {showAddForm ? 'Cancel' : 'Add Participant'}
          </Button>
        )}
      </div>

      {/* 참여자 추가 폼 */}
      {showAddForm && (
        <div className="glass-card p-6 mb-4">
          <h4 className="text-lg font-semibold text-white mb-4">Add Participant</h4>
          <form onSubmit={handleAddParticipants} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white/70 mb-2">
                Team Member
              </label>
              {/* 전체 선택 체크박스 */}
              <div className="mb-2 pb-2 border-b border-white/10">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={selectedUserIds.size === availableMembers.length && availableMembers.length > 0}
                    onChange={handleToggleAll}
                    className="w-4 h-4 text-mit-primary border-white/20 rounded focus:ring-mit-primary/50 bg-white/5"
                  />
                  <span className="text-sm font-medium text-white/80">Select all</span>
                </label>
              </div>
              {/* 멤버 목록 체크박스 */}
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {availableMembers.map((member) => (
                  <label key={member.userId} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      aria-label={member.user?.name || member.user?.email || member.userId}
                      checked={selectedUserIds.has(member.userId)}
                      onChange={() => handleToggleUser(member.userId)}
                      className="w-4 h-4 text-mit-primary border-white/20 rounded focus:ring-mit-primary/50 bg-white/5"
                    />
                    <span className="text-sm text-white">
                      {member.user?.name || member.user?.email}
                    </span>
                  </label>
                ))}
              </div>
              {/* 선택된 멤버 수 표시 */}
              {selectedUserIds.size > 0 && (
                <p className="mt-2 text-sm text-mit-primary">
                  {selectedUserIds.size} selected
                </p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">
                Role
              </label>
              <select
                value={participantRole}
                onChange={(e) => setParticipantRole(e.target.value as ParticipantRole)}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-mit-primary/50"
              >
                <option value="participant" className="bg-gray-800">Participant</option>
                <option value="host" className="bg-gray-800">Host</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button type="submit" isLoading={adding} disabled={selectedUserIds.size === 0}>
                Add
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowAddForm(false)}
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      <div className="glass-card divide-y divide-white/10">
        {participants.map((participant) => (
          <ParticipantRow
            key={participant.id}
            participant={participant}
            currentUserId={currentUserId}
            isHost={isHost}
            isEditing={editingParticipantId === participant.userId}
            editRole={editRole}
            onStartEdit={() => {
              setEditingParticipantId(participant.userId);
              setEditRole(participant.role as ParticipantRole);
            }}
            onCancelEdit={() => setEditingParticipantId(null)}
            onEditRoleChange={setEditRole}
            onSaveRole={() => handleUpdateRole(participant.userId)}
            onRemove={() =>
              onRemoveParticipant(
                participant.userId,
                participant.user?.name || 'this participant'
              )
            }
          />
        ))}
      </div>
    </div>
  );
}

interface ParticipantRowProps {
  participant: MeetingParticipant;
  currentUserId: string | undefined;
  isHost: boolean;
  isEditing: boolean;
  editRole: ParticipantRole;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onEditRoleChange: (role: ParticipantRole) => void;
  onSaveRole: () => void;
  onRemove: () => void;
}

function ParticipantRow({
  participant,
  currentUserId,
  isHost,
  isEditing,
  editRole,
  onStartEdit,
  onCancelEdit,
  onEditRoleChange,
  onSaveRole,
  onRemove,
}: ParticipantRowProps) {
  const isCurrentUser = participant.userId === currentUserId;

  return (
    <div className="p-4 flex items-center justify-between">
      <div>
        <p className="font-medium text-white">
          {participant.user?.name || 'Unknown User'}
          {isCurrentUser && (
            <span className="text-white/50 text-sm ml-2">(You)</span>
          )}
        </p>
        <p className="text-sm text-white/60">
          {participant.user?.email}
        </p>
      </div>
      <div className="flex items-center gap-2">
        {isEditing ? (
          // 역할 수정 모드
          <>
            <select
              value={editRole}
              onChange={(e) => onEditRoleChange(e.target.value as ParticipantRole)}
              className="px-2 py-1 bg-white/5 border border-white/10 rounded text-sm text-white"
            >
              <option value="participant" className="bg-gray-800">Participant</option>
              <option value="host" className="bg-gray-800">Host</option>
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
                PARTICIPANT_ROLE_COLORS[participant.role as ParticipantRole]
              }`}
            >
              {PARTICIPANT_ROLE_LABELS[participant.role as ParticipantRole]}
            </span>
            {/* host는 다른 참여자의 역할 변경 가능 */}
            {isHost && !isCurrentUser && (
              <Button
                variant="outline"
                onClick={onStartEdit}
                className="text-sm px-2 py-1"
              >
                Edit
              </Button>
            )}
            {/* host는 다른 참여자 삭제 가능, 본인은 삭제 가능 */}
            {((isHost && !isCurrentUser) || isCurrentUser) && (
              <Button
                variant="outline"
                onClick={onRemove}
                className="text-sm px-2 py-1 text-red-400 border-red-500/30 hover:bg-red-500/20"
              >
                {isCurrentUser ? 'Leave' : 'Remove'}
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
