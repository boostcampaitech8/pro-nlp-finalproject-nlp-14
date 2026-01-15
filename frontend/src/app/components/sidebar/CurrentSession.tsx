// 현재 세션 표시 카드
import { Link } from 'react-router-dom';
import { Clock, Users, Video } from 'lucide-react';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';

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

  if (!isActive) {
    return (
      <button
        onClick={() => openModal()}
        className="w-full glass-card p-4 hover:bg-white/5 transition-colors group"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-mit-primary/20 to-mit-secondary/20 flex items-center justify-center group-hover:from-mit-primary/30 group-hover:to-mit-secondary/30 transition-colors">
            <Video className="w-5 h-5 text-white/60 group-hover:text-white/80" />
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-white/70 group-hover:text-white/90">
              새 회의 시작
            </p>
            <p className="text-xs text-white/40">
              클릭하여 회의 만들기
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
