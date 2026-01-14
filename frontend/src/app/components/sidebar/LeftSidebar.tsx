// 좌측 사이드바 (280px)
import { useState, useEffect } from 'react';
import { Logo } from './Logo';
import { CurrentSession } from './CurrentSession';
import { Navigation } from './Navigation';
import { MiniCard } from './MiniCard';
import { ScrollArea } from '@/app/components/ui';
import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import { useTeamStore } from '@/stores/teamStore';

export function LeftSidebar() {
  const { meetingId, participants, connectionState } = useMeetingRoomStore();
  const { currentMeeting, fetchMeeting } = useTeamStore();
  const [duration, setDuration] = useState<string>('');
  const [startTime] = useState<Date | null>(null);

  // 회의 정보 로드
  useEffect(() => {
    if (meetingId && !currentMeeting) {
      fetchMeeting(meetingId);
    }
  }, [meetingId, currentMeeting, fetchMeeting]);

  // 회의 시간 업데이트
  useEffect(() => {
    if (!meetingId || connectionState !== 'connected') {
      setDuration('');
      return;
    }

    const start = startTime || new Date();
    const updateDuration = () => {
      const now = new Date();
      const diff = Math.floor((now.getTime() - start.getTime()) / 1000);
      const hours = Math.floor(diff / 3600);
      const minutes = Math.floor((diff % 3600) / 60);
      const seconds = diff % 60;

      if (hours > 0) {
        setDuration(`${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`);
      } else {
        setDuration(`${minutes}:${seconds.toString().padStart(2, '0')}`);
      }
    };

    updateDuration();
    const interval = setInterval(updateDuration, 1000);
    return () => clearInterval(interval);
  }, [meetingId, connectionState, startTime]);

  const isInMeeting = meetingId && connectionState === 'connected';
  const participantCount = participants.size;

  return (
    <aside className="w-[280px] glass-sidebar flex flex-col border-r border-glass">
      {/* 헤더: 로고 + 현재 세션 */}
      <div className="p-5 border-b border-glass">
        <Logo />
        <CurrentSession
          meetingId={meetingId || undefined}
          meetingTitle={currentMeeting?.title}
          participantCount={participantCount}
          duration={duration}
          isActive={!!isInMeeting}
        />
      </div>

      {/* 네비게이션 */}
      <ScrollArea className="flex-1">
        <nav className="p-4">
          <Navigation />
        </nav>
      </ScrollArea>

      {/* 미니 카드 */}
      <div className="p-3 border-t border-glass">
        <MiniCard />
      </div>
    </aside>
  );
}
