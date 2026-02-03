/**
 * 팀 정보 카드 컴포넌트
 * 팀 기본 정보 표시 및 삭제 기능
 */

import { Button } from '@/components/ui/Button';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
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
    <div className="glass-card p-6 mb-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">
            {team.name}
          </h2>
          {team.description && (
            <MarkdownRenderer content={team.description} className="text-white/70 mb-4" />
          )}
          <p className="text-sm text-white/60">
            {team.members.length} member(s) | Your role:{' '}
            <span className="font-medium text-white/80">{currentUserRole}</span>
          </p>
        </div>
        {isOwner && (
          <Button
            variant="outline"
            onClick={onDelete}
            isLoading={deleting}
            className="text-red-400 border-red-500/30 hover:bg-red-500/20"
          >
            Delete Team
          </Button>
        )}
      </div>
    </div>
  );
}
