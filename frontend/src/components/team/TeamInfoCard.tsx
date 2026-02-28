/**
 * 팀 정보 카드 컴포넌트 - 팀 기본 정보 표시, 초대 링크 복사 및 설정 접근
 */

import { useState } from 'react';
import { UserPlus, Check, Settings } from 'lucide-react';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/app/components/ui';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
import { cn } from '@/lib/utils';
import type { TeamRole, TeamWithMembers } from '@/types';

interface TeamInfoCardProps {
  team: TeamWithMembers;
  currentUserRole: TeamRole | undefined;
  onOpenSettings: () => void;
  onShareInvite: () => Promise<boolean>;
}

export function TeamInfoCard({
  team,
  currentUserRole,
  onOpenSettings,
  onShareInvite,
}: TeamInfoCardProps) {
  const [copied, setCopied] = useState(false);

  const handleShareClick = async () => {
    const success = await onShareInvite();
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

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
        <TooltipProvider delayDuration={300}>
          <div className="relative flex flex-col items-end">
            <div className="flex items-center gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={handleShareClick}
                    className={cn(
                      'p-2.5 rounded-xl transition-all duration-200',
                      copied
                        ? 'text-green-400 bg-green-500/15'
                        : 'text-white/60 bg-white/5 hover:text-white hover:bg-white/10'
                    )}
                  >
                    {copied ? (
                      <Check className="w-5 h-5" />
                    ) : (
                      <UserPlus className="w-5 h-5" />
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  팀원 초대 (링크 복사)
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={onOpenSettings}
                    className="p-2.5 rounded-xl bg-white/5 text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                  >
                    <Settings className="w-5 h-5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  팀 설정
                </TooltipContent>
              </Tooltip>
            </div>
            {/* 복사 완료 알림 */}
            <div
              className={cn(
                'absolute -bottom-8 right-0 flex items-center gap-1.5 px-3 py-1 rounded-full bg-green-500/15 border border-green-500/20 text-green-400 text-xs font-medium whitespace-nowrap transition-all duration-300',
                copied
                  ? 'opacity-100 translate-y-0'
                  : 'opacity-0 -translate-y-1 pointer-events-none'
              )}
            >
              <Check className="w-3 h-3" />
              초대 링크가 복사되었습니다!
            </div>
          </div>
        </TooltipProvider>
      </div>
    </div>
  );
}
