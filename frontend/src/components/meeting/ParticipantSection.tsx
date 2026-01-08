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
  const [selectedUserId, setSelectedUserId] = useState('');
  const [participantRole, setParticipantRole] = useState<ParticipantRole>('participant');
  const [adding, setAdding] = useState(false);
  const [editingParticipantId, setEditingParticipantId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<ParticipantRole>('participant');

  const handleAddParticipant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUserId) return;

    setAdding(true);
    try {
      await onAddParticipant(selectedUserId, participantRole);
      setSelectedUserId('');
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
        <h3 className="text-xl font-bold text-gray-900">
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
        <div className="bg-white rounded-xl shadow-md p-6 mb-4">
          <h4 className="text-lg font-semibold mb-4">Add Participant</h4>
          <form onSubmit={handleAddParticipant} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Team Member
              </label>
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select a member</option>
                {availableMembers.map((member) => (
                  <option key={member.userId} value={member.userId}>
                    {member.user?.name || member.user?.email}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Role
              </label>
              <select
                value={participantRole}
                onChange={(e) => setParticipantRole(e.target.value as ParticipantRole)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="participant">Participant</option>
                <option value="host">Host</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button type="submit" isLoading={adding}>
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

      <div className="bg-white rounded-xl shadow-md divide-y">
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
        <p className="font-medium text-gray-900">
          {participant.user?.name || 'Unknown User'}
          {isCurrentUser && (
            <span className="text-gray-500 text-sm ml-2">(You)</span>
          )}
        </p>
        <p className="text-sm text-gray-500">
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
              className="px-2 py-1 border border-gray-300 rounded text-sm"
            >
              <option value="participant">Participant</option>
              <option value="host">Host</option>
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
                className="text-sm px-2 py-1 text-red-600 border-red-300 hover:bg-red-50"
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
