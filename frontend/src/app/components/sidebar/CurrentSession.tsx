// 현재 세션 표시 카드
import { Clock, Users } from 'lucide-react';

interface CurrentSessionProps {
  meetingTitle?: string;
  participantCount?: number;
  duration?: string;
  isActive?: boolean;
}

export function CurrentSession({
  meetingTitle,
  participantCount = 0,
  duration,
  isActive = false,
}: CurrentSessionProps) {
  if (!isActive) {
    return (
      <div className="glass-card p-4">
        <p className="text-sm text-white/50 text-center">
          진행 중인 회의가 없습니다
        </p>
      </div>
    );
  }

  return (
    <div className="glass-card-hover p-4 cursor-pointer">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-2 rounded-full bg-mit-success animate-pulse" />
        <span className="text-[11px] font-medium text-mit-success uppercase tracking-wide">
          Live
        </span>
      </div>

      <h3 className="text-card-title mb-2 line-clamp-1">
        {meetingTitle || '회의 제목'}
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
    </div>
  );
}
