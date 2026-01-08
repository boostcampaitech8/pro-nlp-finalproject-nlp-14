/**
 * 팀 정보 카드 컴포넌트
 * 팀 기본 정보 표시 및 삭제 기능
 */

import { Button } from '@/components/ui/Button';
import type { TeamRole, TeamWithMembers } from '@/types';

interface TeamInfoCardProps {
  team: TeamWithMembers;
  currentUserRole: TeamRole | undefined;
  isOwner: boolean;
  deleting: boolean;
  onDelete: () => void;
}

export function TeamInfoCard({
  team,
  currentUserRole,
  isOwner,
  deleting,
  onDelete,
}: TeamInfoCardProps) {
  return (
    <div className="bg-white rounded-xl shadow-md p-6 mb-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {team.name}
          </h2>
          {team.description && (
            <p className="text-gray-600 mb-4">{team.description}</p>
          )}
          <p className="text-sm text-gray-500">
            {team.members.length} member(s) | Your role:{' '}
            <span className="font-medium">{currentUserRole}</span>
          </p>
        </div>
        {isOwner && (
          <Button
            variant="outline"
            onClick={onDelete}
            isLoading={deleting}
            className="text-red-600 border-red-300 hover:bg-red-50"
          >
            Delete Team
          </Button>
        )}
      </div>
    </div>
  );
}
