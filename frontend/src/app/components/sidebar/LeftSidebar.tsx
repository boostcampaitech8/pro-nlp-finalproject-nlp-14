// 좌측 사이드바 (280px)
import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Info } from 'lucide-react';
import { Logo } from './Logo';
import { CurrentSession } from './CurrentSession';
import { Navigation } from './Navigation';

import { useMeetingRoomStore } from '@/stores/meetingRoomStore';
import { useTeamStore } from '@/stores/teamStore';
import { CreateTeamModal } from './CreateTeamModal';
import { CreateMeetingModal } from './CreateMeetingModal';
import { useCreateTeamModalStore } from '@/app/stores/createTeamModalStore';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';

export function LeftSidebar() {
  const { meetingId, participants, connectionState } = useMeetingRoomStore();
  const { currentMeeting, fetchMeeting } = useTeamStore();
  const { isOpen: isCreateTeamOpen, closeModal: closeCreateTeam } = useCreateTeamModalStore();
  const { isOpen: isMeetingModalOpen, closeModal: closeMeetingModal } = useMeetingModalStore();
  const [duration, setDuration] = useState<string>('');
  const startTimeRef = useRef<Date | null>(null);

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
      startTimeRef.current = null; // 회의 종료 시 초기화
      return;
    }

    // 회의 시작 시 시작 시간 기록 (최초 1회만)
    if (!startTimeRef.current) {
      startTimeRef.current = new Date();
    }

    const start = startTimeRef.current;
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
  }, [meetingId, connectionState]);

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
      <div className="flex-1 min-h-0 overflow-hidden">
        <nav className="h-full">
          <Navigation />
        </nav>
      </div>

      {/* 서비스 소개 + 미니 카드 */}
      <div className="p-3 border-t border-glass space-y-2">
        <Link
          to="/introduce"
          className="block p-3 rounded-xl bg-gradient-to-r from-mit-primary/15 to-mit-purple/15 border border-mit-primary/25 hover:from-mit-primary/25 hover:to-mit-purple/25 hover:border-mit-primary/40 transition-all duration-200 group"
        >
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-mit-primary to-mit-purple flex items-center justify-center flex-shrink-0">
              <Info className="w-3.5 h-3.5 text-white" />
            </div>
            <div>
              <span className="text-[13px] font-semibold text-white group-hover:text-white">
                서비스 소개
              </span>
              <p className="text-[10px] text-white/40">Mit이 처음이신가요?</p>
            </div>
          </div>
        </Link>
        {/* <MiniCard /> */}
      </div>

      {/* 팀 생성 모달 */}
      <CreateTeamModal
        open={isCreateTeamOpen}
        onOpenChange={(open) => !open && closeCreateTeam()}
      />

      {/* 회의 생성 모달 */}
      <CreateMeetingModal
        open={isMeetingModalOpen}
        onOpenChange={(open) => !open && closeMeetingModal()}
      />
    </aside>
  );
}
