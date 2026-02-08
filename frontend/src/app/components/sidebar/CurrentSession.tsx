// 현재 세션 표시 카드
import { Link } from 'react-router-dom';
import { Clock, Users, Video } from 'lucide-react';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { useTeamStore } from '@/stores/teamStore';

interface CurrentSessionProps {
  meetingId?: string;
  meetingTitle?: string;
  participantCount?: number;
  duration?: string;
  isActive?: boolean;
}

export function CurrentSession({
  meetingId,
  meetingTitle,
  participantCount = 0,
  duration,
  isActive = false,
}: CurrentSessionProps) {
  const { openModal } = useMeetingModalStore();
  const { teams, teamsLoading } = useTeamStore();

  if (!isActive) {
    const hasTeams = !teamsLoading && teams.length > 0;

    if (!hasTeams) return null;

    return (
      <button
        onClick={() => openModal()}
        className="w-full p-4 rounded-xl bg-gradient-to-r from-mit-primary/20 to-mit-purple/20 hover:from-mit-primary/30 hover:to-mit-purple/30 border border-mit-primary/25 hover:border-mit-primary/40 transition-all group"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-mit-primary to-mit-purple flex items-center justify-center">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-white">
              새 회의 시작
            </p>
            <p className="text-xs text-white/40 group-hover:text-white/60 transition-colors">
              팀원과 회의 시작
            </p>
          </div>
        </div>
      </button>
    );
  }

  return (
    <Link
      to={`/dashboard/meetings/${meetingId}/room`}
      className="block glass-card-hover p-4"
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-2 rounded-full bg-mit-success animate-pulse" />
        <span className="text-[11px] font-medium text-mit-success uppercase tracking-wide">
          Live
        </span>
      </div>

      <h3 className="text-card-title mb-2 line-clamp-1">
        {meetingTitle || '회의 진행 중'}
      </h3>

      <div className="flex items-center gap-4 text-meta">
        <div className="flex items-center gap-1">
          <Users className="w-3.5 h-3.5" />
          <span>{participantCount}명 참여</span>
        </div>
        {duration && (
          <div className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            <span>{duration}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
